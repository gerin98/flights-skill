"""Shared search inputs, validation, and Google Flights query construction."""

from dataclasses import asdict, dataclass
from datetime import date as Date
import re

from fast_flights import FlightQuery, Passengers, create_query


CABINS = ("economy", "premium-economy", "business", "first")
COUNT_LIMITS = {
    "adults": (1, 9),
    "children": (0, 8),
    "infants_in_seat": (0, 8),
    "infants_on_lap": (0, 4),
    "carry_on_bags": (0, 1),
    "checked_bags": (0, 2),
}
PASSENGER_FIELDS = ("adults", "children", "infants_in_seat", "infants_on_lap")


def _date(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{name} must be a date in YYYY-MM-DD format")
    try:
        return Date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a valid calendar date") from error


# These fields are the independent user-facing search options.
@dataclass(kw_only=True)
class SearchRequest:  # pylint: disable=too-many-instance-attributes
    """A validated one-way or round-trip search for an accompanied passenger group."""

    origin: str
    destination: str
    date: str
    return_date: str | None = None
    cabin: str = "economy"
    adults: int = 1
    children: int = 0
    infants_in_seat: int = 0
    infants_on_lap: int = 0
    carry_on_bags: int = 0
    checked_bags: int = 0

    def __post_init__(self):
        for name in ("origin", "destination"):
            value = getattr(self, name)
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{3}", value):
                raise ValueError(f"{name} must be a three-letter airport code")
            setattr(self, name, value.upper())
        if self.origin == self.destination:
            raise ValueError("origin and destination must be different airports")
        departure = _date(self.date, "date")
        if self.return_date is not None and _date(self.return_date, "return_date") < departure:
            raise ValueError("return_date must be on or after date")
        if self.cabin not in CABINS:
            raise ValueError(f"cabin must be one of: {', '.join(CABINS)}")
        for name, (minimum, maximum) in COUNT_LIMITS.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
            if not minimum <= value <= maximum:
                raise ValueError(f"{name} must be between {minimum} and {maximum}")
        if sum(getattr(self, name) for name in PASSENGER_FIELDS) > 9:
            raise ValueError("At most 9 passengers are supported, including infants")
        if self.infants_on_lap > self.adults:
            raise ValueError("Each infant on lap must have an accompanying adult")

    @property
    def trip_type(self):
        """Infer trip type from the presence of a return date."""
        return "round-trip" if self.return_date is not None else "one-way"

    def query(self):
        """Build the upstream query with every requested passenger and baggage option."""
        flights = [FlightQuery(
            date=self.date, from_airport=self.origin, to_airport=self.destination,
        )]
        if self.return_date is not None:
            flights.append(FlightQuery(
                date=self.return_date, from_airport=self.destination, to_airport=self.origin,
            ))
        return create_query(
            flights=flights,
            trip=self.trip_type,
            seat=self.cabin,
            passengers=Passengers(**{name: getattr(self, name) for name in PASSENGER_FIELDS}),
            carry_on_bags=self.carry_on_bags,
            checked_bags=self.checked_bags,
            language="en",
            currency="USD",
        )

    def metadata(self):
        """Echo the search so fares cannot be confused with another party or trip type."""
        return {**asdict(self), "trip_type": self.trip_type}

    def notes(self, *, return_options=False):
        """Explain the scope of Google's fares and the initial flight selection."""
        notes = ["Prices are Google's quoted totals for all requested passengers in USD."]
        if return_options:
            notes.append(
                "Each return option is priced with selected_outbound as one round trip. "
                "The price covers both directions for all requested passengers. "
                "Use its booking_token with get_booking_details for fare-specific bag and "
                "seat-selection information, or open booking_url to finish manually."
            )
        elif self.return_date is not None:
            notes.append(
                "Round-trip fares are shown with outbound flight options only. "
                "Durations and segments describe the outbound journey. Select a return flight "
                "using search_return_flights with its return_search_token, or open "
                "return_search_url to choose manually."
            )
        if self.carry_on_bags or self.checked_bags:
            notes.append(
                "Baggage filters were requested, but the response does not verify bag allowances "
                "or all bag fees. Confirm them with the airline before booking."
            )
        if self.cabin != "economy":
            notes.append(
                "Cabin is a search preference. Google may include mixed-cabin connections; "
                "confirm the cabin of each segment before booking."
            )
        return notes


SEARCH_PROPERTIES = {
    "origin": {"type": "string", "description": "Origin airport code, e.g. JFK"},
    "destination": {"type": "string", "description": "Destination airport code, e.g. CDG"},
    "date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
    "return_date": {
        "type": "string",
        "description": "Return date (YYYY-MM-DD). Omit for one-way; include for round-trip.",
    },
    "cabin": {
        "type": "string", "enum": list(CABINS), "default": "economy",
        "description": "Cabin class preference, not selection of a specific seat.",
    },
    "adults": {"description": "Adults. At least one; at most 9 passengers total."},
    "children": {"description": "Children aged 2–11."},
    "infants_in_seat": {"description": "Infants under 2 occupying their own seats."},
    "infants_on_lap": {"description": "Infants under 2 on laps. At most one per adult."},
    "carry_on_bags": {
        "description": "Requested carry-on bag filter (0 or 1). Fee inclusion is not verified.",
    },
    "checked_bags": {
        "description": "Requested checked-bag filter (0–2). Fee inclusion is not verified.",
    },
}
for _name, (_minimum, _maximum) in COUNT_LIMITS.items():
    SEARCH_PROPERTIES[_name].update({
        "type": "integer", "minimum": _minimum, "maximum": _maximum,
        "default": getattr(SearchRequest, _name),
    })

SEARCH_SCHEMA = {
    "type": "object",
    "properties": SEARCH_PROPERTIES,
    "required": ["origin", "destination", "date"],
    "additionalProperties": False,
}
