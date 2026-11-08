"""Exercise flight parsing and both interfaces using synthetic Google responses."""

# Test method names describe the behavior without repetitive docstrings.
# pylint: disable=missing-function-docstring
# Each CLI test keeps its short stdout/argv setup visible in the test itself.
# pylint: disable=duplicate-code

from contextlib import redirect_stdout
from io import StringIO
import json
import sys
import unittest
from unittest.mock import patch

import flight_search
import mcp_server
import search


# The fixture mirrors the independent fields of a Google flight leg.
# pylint: disable-next=too-many-arguments
def leg(*, origin="JFK", destination="SFO", departure_date=None, departure_time=None,
        arrival_date=None, arrival_time=None, duration=407):
    """A synthetic Google flight leg in the format consumed by fast-flights."""
    segment = [None] * 22
    segment[3:7] = [origin, origin, destination, destination]
    segment[8] = [21] if departure_time is None else departure_time
    segment[10] = [None, 47] if arrival_time is None else arrival_time
    segment[11] = duration
    segment[17] = "Airbus A321"
    segment[20] = departure_date or [2026, 12, 1]
    segment[21] = arrival_date or [2026, 12, 2]
    return segment


def itinerary(segments=None, price=364, duration=407):
    """Build an itinerary with an optional fare and total journey duration."""
    flight = [None] * 23
    flight[0:3] = ["AA", ["American"], [leg()] if segments is None else segments]
    flight[9] = duration
    flight[22] = [None] * 7 + [383000, 371000]
    return [flight, [[None, price]] if price is not None else None]


def response(best=None, remaining=None):
    """Wrap the two result groups in Google's structured response script."""
    payload = [None] * 8
    payload[2] = [best] if best is not None else None
    payload[3] = [remaining] if remaining is not None else None
    payload[7] = [None, [[], [["AA", "American"]]]]
    return (
        '<script class="ds:1">AF_initDataCallback({data:'
        + json.dumps(payload)
        + ', sideChannel: {}});</script>'
    )


class FlightSearchTests(unittest.TestCase):
    """Check query parameters, parsing, and CLI/MCP result serialization."""
    @patch("flight_search.fetch_flights_html")
    def test_usd_query_and_overnight_flight(self, fetch):
        fetch.return_value = response(best=[itinerary()])
        result = flight_search.search_flights("JFK", "SFO", "2026-12-01")
        query = fetch.call_args.args[0]
        self.assertEqual(query.params()["curr"], "USD")
        self.assertEqual(query.params()["hl"], "en")
        self.assertEqual(query.params()["tfu"], "EgQIABABIgA")
        self.assertEqual(query.get_trip_type(), "one-way")
        self.assertEqual(query.get_seat_type(), "economy")
        self.assertEqual(len(query.passengers), 1)
        self.assertEqual(query.flight_data[0].from_airport.airport, "JFK")
        self.assertEqual(query.flight_data[0].to_airport.airport, "SFO")
        self.assertEqual(query.flight_data[0].date, "2026-12-01")
        self.assertEqual(set(result), {"currency", "current_price", "flights"})
        self.assertEqual(result["currency"], "USD")
        flight = result["flights"][0]
        self.assertEqual(flight["name"], "American")
        self.assertEqual(flight["price"], "$364")
        self.assertEqual(flight["duration"], "6 hr 47 min")
        self.assertEqual(flight["duration_minutes"], 407)
        self.assertEqual(flight["departure"], "2026-12-01T21:00")
        self.assertEqual(flight["arrival"], "2026-12-02T00:47")
        self.assertEqual(flight["stops"], 0)
        self.assertEqual(flight["segments"][0]["duration_minutes"], 407)

    @patch("flight_search.fetch_flights_html")
    def test_total_includes_overnight_layover_and_time_zone_difference(self, fetch):
        fetch.return_value = response(remaining=[itinerary(duration=1165, price=314, segments=[
            leg(destination="PDX", departure_time=[16, 35], arrival_date=[2026, 12, 1],
                arrival_time=[20, 8], duration=393),
            leg(origin="PDX", departure_date=[2026, 12, 2], departure_time=[7],
                arrival_time=[9], duration=120),
        ])])
        flight = flight_search.search_flights("JFK", "SFO", "2026-12-01")["flights"][0]
        self.assertEqual(flight["stops"], 1)
        self.assertEqual(flight["duration"], "19 hr 25 min")
        self.assertEqual(flight["duration_minutes"], 1165)
        self.assertEqual(flight["arrival"], "2026-12-02T09:00")
        self.assertEqual([s["duration_minutes"] for s in flight["segments"]], [393, 120])
        self.assertEqual(flight["segments"][1]["origin"], "PDX")

    @patch("flight_search.fetch_flights_html")
    def test_best_and_remaining_groups_keep_matching_durations_and_missing_fares(self, fetch):
        fetch.return_value = response(
            best=[itinerary(price=364, duration=407)],
            remaining=[itinerary(price=379, duration=415), itinerary(price=None, duration=420)],
        )
        flights = flight_search.search_flights("JFK", "SFO", "2026-12-01")["flights"]
        self.assertEqual([f["price"] for f in flights], ["$364", "$379", None])
        self.assertEqual([f["duration_minutes"] for f in flights], [407, 415, 420])

    @patch("flight_search.fetch_flights_html", return_value=response(best=[], remaining=[]))
    def test_empty_results(self, _fetch):
        result = flight_search.search_flights("JFK", "SFO", "2026-12-01")
        self.assertEqual(result, {"currency": "USD", "current_price": None, "flights": []})

    @patch("flight_search.fetch_flights_html")
    def test_price_assessment_from_same_page(self, fetch):
        for markup, expected in (
            ('<span class="gOatQ">low</span>', "low"),
            ('<span class="gOatQ"> Typical </span>', "typical"),
            ('<span class="gOatQ">high</span>', "high"),
            ('', None),
            ('<span class="gOatQ"></span>', None),
            ('<span class="gOatQ">unknown</span>', None),
            ('<span class="changed">typical</span>', None),
        ):
            with self.subTest(markup=markup):
                fetch.reset_mock()
                fetch.return_value = response(best=[itinerary()]) + markup
                result = flight_search.search_flights("JFK", "SFO", "2026-12-01")
                self.assertEqual(result["current_price"], expected)
                self.assertEqual(len(result["flights"]), 1)
                fetch.assert_called_once()

    @patch("flight_search.fetch_flights_html")
    def test_invalid_total_is_not_replaced_with_flying_time(self, fetch):
        for duration in (None, -1, 100, "407", True):
            with self.subTest(duration=duration):
                fetch.return_value = response(best=[itinerary(duration=duration)])
                with self.assertRaisesRegex(ValueError, "invalid total duration"):
                    flight_search.search_flights("JFK", "SFO", "2026-12-01")

    @patch("flight_search.fetch_flights_html", return_value="<html>No flight data</html>")
    def test_unexpected_page_has_a_clear_error(self, _fetch):
        with self.assertRaisesRegex(ValueError, "contains no flight data"):
            flight_search.search_flights("JFK", "SFO", "2026-12-01")

    @patch("flight_search.fetch_flights_html")
    def test_mcp_limits_results_but_cli_returns_all(self, fetch):
        fetch.return_value = (
            response(best=[itinerary() for _ in range(12)])
            + '<span class="gOatQ">typical</span>'
        )
        request = {"jsonrpc": "2.0", "id": 42, "method": "tools/call", "params": {
            "name": "search_flights", "arguments": {
                "origin": "JFK", "destination": "SFO", "date": "2026-12-01",
            },
        }}
        reply = mcp_server.handle_request(request)
        self.assertEqual(reply["id"], 42)
        data = json.loads(reply["result"]["content"][0]["text"])
        self.assertEqual(set(data), {"currency", "current_price", "flights"})
        self.assertEqual(data["current_price"], "typical")
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(len(data["flights"]), 10)
        self.assertEqual(data["flights"][0]["duration_minutes"], 407)
        output = StringIO()
        with (
            patch.object(sys, "argv", ["search.py", "JFK", "SFO", "2026-12-01"]),
            redirect_stdout(output),
        ):
            search.main()
        cli_data = json.loads(output.getvalue())
        self.assertEqual(set(cli_data), {"currency", "current_price", "flights"})
        self.assertEqual(cli_data["current_price"], "typical")
        self.assertEqual(len(cli_data["flights"]), 12)

    @patch("flight_search.fetch_flights_html", side_effect=RuntimeError("Search unavailable"))
    def test_mcp_reports_upstream_errors(self, _fetch):
        reply = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "search_flights", "arguments": {
                    "origin": "JFK", "destination": "SFO", "date": "2026-12-01",
                },
            },
        })
        self.assertEqual(reply["error"]["message"], "Search unavailable")
        self.assertNotIn("result", reply)


if __name__ == "__main__":
    unittest.main()
