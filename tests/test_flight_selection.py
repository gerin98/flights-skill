"""Ensure continuation tokens preserve the trip and return fares match the outbound."""

# pylint: disable=missing-function-docstring

from base64 import urlsafe_b64encode
import json
import unittest
from unittest.mock import patch

import mcp_server
from flight_search import search_flights, search_return_flights
from flight_selection import decode_selection, encode_selection, raw_selection, selected_query
from search_options import SearchRequest
from tests.test_flight_search import itinerary, leg, response


class FlightSelectionTests(unittest.TestCase):
    """Exercise search-to-return continuation with real upstream parsing."""

    def setUp(self):
        self.request = SearchRequest(
            origin="JFK", destination="SFO", date="2026-12-01", return_date="2026-12-10",
            adults=2, cabin="business", checked_bags=1,
        )
        self.outbound = itinerary()[0]
        self.selected = raw_selection(self.outbound)
        self.token = encode_selection(self.request, [self.selected])
        self.return_flight = itinerary(price=831, duration=400, segments=[leg(
            origin="SFO", destination="JFK", departure_date=[2026, 12, 10],
            arrival_date=[2026, 12, 10], duration=400,
        )])

    def test_token_preserves_options_and_encodes_selected_segment(self):
        request, selections = decode_selection(self.token)
        self.assertEqual(request, self.request)
        self.assertEqual(selections, [self.selected])
        query = selected_query(request, selections)
        expected_segment = (
            b'\x0a\x03JFK\x12\x0a2026-12-01\x1a\x03SFO\x2a\x02AA\x32\x03100'
        )
        encoded_field = b'\x22' + bytes([len(expected_segment)]) + expected_segment
        self.assertIn(encoded_field, query.flight_data[0].SerializeToString())
        self.assertNotIn(encoded_field, query.flight_data[1].SerializeToString())
        self.assertEqual(query.passengers, [1, 1])
        self.assertEqual(query.get_seat_type(), "business")
        self.assertEqual(query.pb().baggage.checked_bags, 1)

    @patch("flight_search.fetch_flights_html")
    def test_matching_return_has_combined_fare_and_complete_booking_link(self, fetch):
        fetch.return_value = response(best=[self.return_flight], selected=self.outbound)
        reply = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                "name": "search_return_flights", "arguments": {"selection_token": self.token},
            },
        })
        result = json.loads(reply["result"]["content"][0]["text"])
        self.assertEqual(result["result_scope"], "return_options")
        self.assertEqual(result["price_scope"], "round-trip_all_passengers")
        self.assertEqual(result["selected_outbound"]["segments"][0]["origin"], "JFK")
        self.assertNotIn("price", result["selected_outbound"])
        returning = result["flights"][0]
        self.assertEqual(returning["price"], "$831")
        self.assertEqual(returning["segments"][0]["origin"], "SFO")
        self.assertEqual(returning["duration_minutes"], 400)
        request, selected = decode_selection(returning["booking_token"])
        self.assertEqual(len(selected), 2)
        self.assertEqual(selected[0], self.selected)
        self.assertEqual(selected[1], raw_selection(self.return_flight[0]))
        self.assertEqual(returning["booking_url"], selected_query(request, selected).url())

    @patch("flight_search.fetch_flights_html")
    def test_unconfirmed_outbound_is_rejected(self, fetch):
        wrong = itinerary(segments=[leg(destination="LAX")])[0]
        for selected in (None, wrong):
            with self.subTest(selected=selected):
                fetch.return_value = response(best=[self.return_flight], selected=selected)
                with self.assertRaisesRegex(ValueError, "did not confirm"):
                    search_return_flights(self.token)

    @patch("flight_search.fetch_flights_html")
    def test_outbound_and_one_way_results_have_correct_continuations(self, fetch):
        fetch.return_value = response(best=[itinerary()])
        round_trip = search_flights("JFK", "SFO", "2026-12-01", return_date="2026-12-10")
        self.assertIn("return_search_token", round_trip["flights"][0])
        one_way = search_flights("JFK", "SFO", "2026-12-01")
        self.assertIn("booking_token", one_way["flights"][0])
        self.assertIn("booking_url", one_way["flights"][0])

    @patch("flight_search.fetch_flights_html")
    def test_invalid_or_wrong_stage_tokens_do_not_fetch(self, fetch):
        one_way = SearchRequest(origin="JFK", destination="SFO", date="2026-12-01")
        for token in ("bad", "x" * 24001, encode_selection(one_way, [self.selected])):
            with self.subTest(token=token[:20]), self.assertRaises(ValueError):
                search_return_flights(token)
        fetch.assert_not_called()

    def test_untrusted_token_cannot_supply_urls_or_unrelated_flights(self):
        bad = {"version": 1, "search": self.request.metadata(), "selections": [self.selected]}
        bad["search"].pop("trip_type")
        bad["url"] = "http://localhost/private"
        with self.assertRaises(ValueError):
            decode_selection(urlsafe_b64encode(json.dumps(bad).encode()).decode())
        for change in ({"origin": "LAX"}, {"date": "2026-12-02"}, {"airline": "https://x"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                encode_selection(self.request, [[self.selected[0] | change]])

    def test_connection_preserves_next_day_segment_identity(self):
        outbound = itinerary(duration=1000, segments=[
            leg(destination="LAX"),
            leg(origin="LAX", departure_date=[2026, 12, 2]),
        ])[0]
        selection = raw_selection(outbound)
        token = encode_selection(self.request, [selection])
        self.assertEqual(decode_selection(token)[1][0][1]["date"], "2026-12-02")
        query = selected_query(self.request, [selection])
        self.assertIn(b"2026-12-02", query.flight_data[0].SerializeToString())


if __name__ == "__main__":
    unittest.main()
