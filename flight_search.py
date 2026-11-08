"""Shared fast-flights v3 query and JSON conversion for the CLI and MCP server."""

from datetime import datetime
import json

from fast_flights import fetch_flights_html
from fast_flights.model import Flights, SimpleDatetime
from fast_flights.parser import parse_js
from selectolax.lexbor import LexborHTMLParser

from search_options import SearchRequest


def _parse_results(parser: LexborHTMLParser) -> list[tuple[Flights, int]]:
    script = parser.css_first(r"script.ds\:1")
    if script is None:
        raise ValueError("Google Flights response contains no flight data")
    javascript = script.text()
    flights = parse_js(javascript)

    # Use the same payload and group order as the pinned fast-flights parser.
    # Its model discards flight[9], Google's total minutes including layovers.
    # Reading that value avoids calculating elapsed time from offset-free dates.
    payload = json.loads(javascript.split("data:", 1)[1].rsplit(",", 1)[0])
    durations = [
        entry[0][9]
        for section in payload[2:4] if section
        for entry in section[0] or []
    ]
    return list(zip(flights, durations, strict=True))


def _local_datetime(value: SimpleDatetime) -> str:
    # v3 supplies airport-local dates and times, without a timezone or UTC offset.
    return datetime(*value.date, *value.time).isoformat(timespec="minutes")


def _duration(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    return f"{hours} hr {remainder} min" if hours else f"{remainder} min"


def _serialize_flight(flight: Flights, total_minutes: int) -> dict:
    if not flight.flights:
        raise ValueError("Flight itinerary has no segments")
    # Exact type checking also rejects bool, which is an int subclass.
    if (
        type(total_minutes) is not int  # pylint: disable=unidiomatic-typecheck
        or total_minutes < sum(leg.duration for leg in flight.flights)
    ):
        raise ValueError("Google Flights itinerary has an invalid total duration")

    segments = [
        {
            "origin": leg.from_airport.code,
            "destination": leg.to_airport.code,
            "departure": _local_datetime(leg.departure),
            "arrival": _local_datetime(leg.arrival),
            "duration_minutes": leg.duration,
        }
        for leg in flight.flights
    ]
    return {
        "name": ", ".join(flight.airlines),
        "price": f"${flight.price:,}" if flight.price is not None else None,
        "duration": _duration(total_minutes),
        "duration_minutes": total_minutes,
        "departure": segments[0]["departure"],
        "arrival": segments[-1]["arrival"],
        "stops": len(segments) - 1,
        "segments": segments,
    }


def search_flights(
    origin: str, destination: str, date: str, *, limit: int | None = None, **options,
) -> dict:
    """Return USD fares, full journey durations, and Google's search price assessment."""
    request = SearchRequest(origin=origin, destination=destination, date=date, **options)
    query = request.query()
    parser = LexborHTMLParser(fetch_flights_html(query))
    results = _parse_results(parser)
    # The v3 model omits Google's search-wide price assessment in the HTML.
    price_node = parser.css_first("span.gOatQ")
    current_price = price_node.text(strip=True).lower() if price_node else None
    if current_price not in {"low", "typical", "high"}:
        current_price = None
    return {
        "currency": "USD",
        "current_price": current_price,
        "search": request.metadata(),
        "search_url": query.url(),
        "price_scope": f"{request.trip_type}_all_passengers",
        "result_scope": "outbound_options" if request.return_date else "one_way_itineraries",
        "notes": request.notes(),
        "flights": [_serialize_flight(flight, duration) for flight, duration in results[:limit]],
    }
