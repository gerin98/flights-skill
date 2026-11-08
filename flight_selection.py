"""Carry selected flight identities between search, returns, and booking details."""

from base64 import b64decode, urlsafe_b64encode
from dataclasses import asdict
from datetime import date as Date
import json
import re

from search_options import SearchRequest


def raw_selection(flight):
    """Read flight numbers and local dates omitted by the upstream typed model."""
    try:
        return [{
            "origin": leg[3], "destination": leg[6],
            "date": Date(*leg[20]).isoformat(),
            "airline": leg[22][0], "flight_number": leg[22][1],
        } for leg in flight[2]]
    except (IndexError, TypeError, ValueError) as error:
        raise ValueError("Google did not provide selectable flight identifiers") from error


def _validate_selection(segments, origin, destination, date):
    if not isinstance(segments, list) or not 1 <= len(segments) <= 8:
        raise ValueError("A selection must contain between 1 and 8 flight segments")
    previous_airport, previous_date = origin, date
    for index, segment in enumerate(segments):
        patterns = {
            "origin": r"[A-Z]{3}", "destination": r"[A-Z]{3}", "date": r"\d{4}-\d{2}-\d{2}",
            "airline": r"[A-Z0-9]{2,3}", "flight_number": r"[A-Z0-9]{1,6}",
        }
        if not isinstance(segment, dict) or set(segment) != set(patterns):
            raise ValueError("Invalid selected flight fields")
        for name, pattern in patterns.items():
            if not isinstance(segment[name], str) or not re.fullmatch(pattern, segment[name]):
                raise ValueError(f"Invalid selected flight {name}")
        Date.fromisoformat(segment["date"])
        if segment["origin"] != previous_airport or segment["date"] < previous_date:
            raise ValueError("Selected flight segments do not form the requested journey")
        if index == 0 and segment["date"] != date:
            raise ValueError("Selected flight date does not match the search")
        previous_airport, previous_date = segment["destination"], segment["date"]
    if previous_airport != destination:
        raise ValueError("Selected flight destination does not match the search")


def validate_selections(request, selections):
    """Reject malformed or unrelated selections before making network requests."""
    maximum = 2 if request.return_date else 1
    if not isinstance(selections, list) or not 1 <= len(selections) <= maximum:
        raise ValueError("Invalid number of selected journeys")
    _validate_selection(selections[0], request.origin, request.destination, request.date)
    if len(selections) == 2:
        _validate_selection(selections[1], request.destination, request.origin, request.return_date)


def encode_selection(request, selections):
    """Create a stateless continuation token containing only search and flight identifiers."""
    validate_selections(request, selections)
    data = {"version": 1, "search": asdict(request), "selections": selections}
    return urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode()


def decode_selection(token):
    """Decode untrusted input without accepting arbitrary URLs or executable data."""
    if not isinstance(token, str) or len(token) > 24000:
        raise ValueError("Invalid flight selection token")
    try:
        data = json.loads(b64decode(token, altchars=b"-_", validate=True))
        if not isinstance(data, dict) or set(data) != {"version", "search", "selections"}:
            raise ValueError("Invalid token fields")
        if data["version"] != 1:
            raise ValueError("Unsupported token version")
        request = SearchRequest(**data["search"])
        validate_selections(request, data["selections"])
        return request, data["selections"]
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        raise ValueError("Invalid flight selection token; run a new search") from error


def _varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _field(number, value):
    return _varint(number * 8 + 2) + _varint(len(value)) + value


def selected_query(request, selections):
    """Add Google's selected-flight field, which upstream's protobuf does not expose."""
    validate_selections(request, selections)
    query = request.query()
    for index, segments in enumerate(selections):
        for segment in segments:
            # FlightData field 4 is a selected segment. Protobuf preserves unknown fields.
            # Its fields identify origin, local date, destination, airline, and flight number.
            encoded = b"".join(_field(number, segment[name].encode()) for number, name in (
                (1, "origin"), (2, "date"), (3, "destination"),
                (5, "airline"), (6, "flight_number"),
            ))
            query.flight_data[index].MergeFromString(_field(4, encoded))
    return query
