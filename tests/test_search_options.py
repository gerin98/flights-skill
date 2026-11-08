"""Validate search options and their representation in the upstream query."""

# Test names describe the assertions without repetitive docstrings.
# pylint: disable=missing-function-docstring

from dataclasses import fields
import unittest

import mcp_server
from search_options import CABINS, SEARCH_SCHEMA, SearchRequest


class SearchOptionsTests(unittest.TestCase):
    """Keep defaults, input validation, and the advertised tool schema consistent."""

    def test_schema_matches_supported_options_and_defaults(self):
        reply = mcp_server.handle_request({"id": 1, "method": "tools/list"})
        schema = reply["result"]["tools"][0]["inputSchema"]
        self.assertEqual(schema, SEARCH_SCHEMA)
        self.assertEqual(set(schema["properties"]), {f.name for f in fields(SearchRequest)})
        for name, spec in schema["properties"].items():
            if "default" in spec:
                self.assertEqual(spec["default"], getattr(SearchRequest, name))
        self.assertFalse(schema["additionalProperties"])

    def test_all_cabins_and_same_day_return(self):
        for cabin in CABINS:
            with self.subTest(cabin=cabin):
                request = SearchRequest(
                    origin="jfk", destination="sfo", date="2027-05-01",
                    return_date="2027-05-01", cabin=cabin,
                )
                query = request.query()
                self.assertEqual(query.get_seat_type(), cabin)
                self.assertEqual(query.get_trip_type(), "round-trip")
                self.assertEqual(len(query.flight_data), 2)

    def test_invalid_dates_airports_and_option_types(self):
        for options in (
            {"date": "2027-02-29"}, {"date": "20270501"}, {"date": 20270501},
            {"date": "2027-5-1"}, {"return_date": ""}, {"return_date": "2027-04-30"},
            {"origin": "New York"}, {"destination": "JFK"}, {"origin": "１２３"},
            {"adults": "2"}, {"children": None}, {"cabin": None},
            {"checked_bags": True}, {"carry_on_bags": -1},
        ):
            with self.subTest(options=options):
                args = {"origin": "JFK", "destination": "CDG", "date": "2027-05-01"}
                with self.assertRaises(ValueError):
                    SearchRequest(**(args | options))

    def test_passenger_boundaries(self):
        request = SearchRequest(
            origin="JFK", destination="CDG", date="2027-05-01",
            adults=4, children=1, infants_on_lap=4,
        )
        self.assertEqual(len(request.query().passengers), 9)
        for options in ({"adults": 0}, {"adults": 2, "children": 8}, {"infants_on_lap": 2}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                SearchRequest(origin="JFK", destination="CDG", date="2027-05-01", **options)


if __name__ == "__main__":
    unittest.main()
