"""Shared fast-flights v3 query and JSON conversion for the CLI and MCP server."""

from datetime import datetime
import json

from fast_flights import fetch_flights_html
from fast_flights.model import Flights, SimpleDatetime
from fast_flights.parser import parse_js
from selectolax.lexbor import LexborHTMLParser

from search_options import SearchRequest
from flight_selection import decode_selection, encode_selection, raw_selection, selected_query


def _page_data(parser):
    script = parser.css_first(r"script.ds\:1")
    if script is None:
        raise ValueError("Google Flights response contains no flight data")
    javascript = script.text()
    payload = json.loads(javascript.split("data:", 1)[1].rsplit(",", 1)[0])
    return javascript, payload


def _parse_results(parser: LexborHTMLParser) -> list[tuple[Flights, list]]:
    javascript, payload = _page_data(parser)
    flights = parse_js(javascript)
    # Preserve total duration and selectable flight identities omitted by the v3 model.
    raw_flights = [
        entry[0]
        for section in payload[2:4] if section
        for entry in section[0] or []
    ]
    return list(zip(flights, raw_flights, strict=True))


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


def _serialize_result(flight, raw):
    result = _serialize_flight(flight, raw[9])
    try:
        for segment, identity in zip(result["segments"], raw_selection(raw), strict=True):
            segment.update({
                "airline": identity["airline"], "flight_number": identity["flight_number"],
            })
    except ValueError:
        pass  # The basic result can still be shown when Google omits selectable identifiers.
    return result


def _add_selection(result, raw, request, selected=None):
    selections = [*(selected or []), raw_selection(raw)]
    token = encode_selection(request, selections)
    complete = len(selections) == (2 if request.return_date else 1)
    result["booking_token" if complete else "return_search_token"] = token
    result["booking_url" if complete else "return_search_url"] = (
        selected_query(request, selections).url()
    )


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
    flights = []
    for flight, raw in results[:limit]:
        result = _serialize_result(flight, raw)
        try:
            _add_selection(result, raw, request)
        except ValueError:
            result["selection_unavailable"] = True
        flights.append(result)
    return {
        "currency": "USD",
        "current_price": current_price,
        "search": request.metadata(),
        "search_url": query.url(),
        "price_scope": f"{request.trip_type}_all_passengers",
        "result_scope": "outbound_options" if request.return_date else "one_way_itineraries",
        "notes": request.notes(),
        "flights": flights,
    }


def _selected_outbound(parser, expected_selection):
    _, payload = _page_data(parser)
    try:
        outbound_raw = payload[1][0][2]
        if raw_selection(outbound_raw) != expected_selection:
            raise ValueError("Outbound selection did not match")
    except (IndexError, TypeError, ValueError) as error:
        raise ValueError(
            "Google did not confirm the selected outbound; run a new search"
        ) from error
    # Reuse upstream's parser for the selected outbound with no independent fare attached.
    selected_payload = [None] * 8
    selected_payload[2] = [[[outbound_raw, None]]]
    selected_payload[7] = payload[7]
    outbound = parse_js("data:" + json.dumps(selected_payload) + ", sideChannel: {}")[0]
    selected_outbound = _serialize_result(outbound, outbound_raw)
    selected_outbound.pop("price")
    return selected_outbound


def search_return_flights(selection_token: str, *, limit: int | None = None) -> dict:
    """Retrieve return options priced together with one specific outbound selection."""
    request, selections = decode_selection(selection_token)
    if not request.return_date or len(selections) != 1:
        raise ValueError("Use a return_search_token from a round-trip outbound result")
    query = selected_query(request, selections)
    parser = LexborHTMLParser(fetch_flights_html(query))
    selected_outbound = _selected_outbound(parser, selections[0])
    flights = []
    for flight, raw in _parse_results(parser)[:limit]:
        result = _serialize_result(flight, raw)
        _add_selection(result, raw, request, selections)
        flights.append(result)
    return {
        "currency": "USD", "search": request.metadata(), "search_url": query.url(),
        "price_scope": "round-trip_all_passengers", "result_scope": "return_options",
        "selected_outbound": selected_outbound, "flights": flights,
        "notes": request.notes(return_options=True),
    }
