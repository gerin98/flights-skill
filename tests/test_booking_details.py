"""Verify fare-specific bag and seat terms without running a browser in CI."""

# pylint: disable=missing-function-docstring

import unittest
from unittest.mock import patch

from booking_details import get_booking_details
from flight_selection import encode_selection
from search_options import SearchRequest


def fare_html(name="Basic", price=830, seat="No seat selection", bag=None):
    """A small representative fare card including its accessibility-only bag price."""
    baggage = bag or (
        '<span class="HeMQ4">First checked bag costs 150 US dollars</span>'
        '<span aria-hidden="true">1st checked bag: $150</span>'
    )
    return f'''<div><div><h3 class="DllrY">{name}</h3></div>
        <span class="hEkLUb">{seat}</span><span class="hEkLUb">No refunds</span>
        <ul jsname="vNB5le"><li>1 free carry-on</li><li>{baggage}</li></ul>
        <button aria-label="Continue to book with Delta, {name} for {price} US dollars">
        Continue</button></div>'''


class BookingDetailsTests(unittest.TestCase):
    """Keep fare price, ancillary terms, and manual booking distinct."""

    def setUp(self):
        self.request = SearchRequest(origin="JFK", destination="SFO", date="2026-12-01")
        self.selections = [[{
            "origin": "JFK", "destination": "SFO", "date": "2026-12-01",
            "airline": "DL", "flight_number": "123",
        }]]
        self.token = encode_selection(self.request, self.selections)

    @patch("booking_details._fetch_booking_pages")
    def test_distinct_fares_include_actual_bag_and_seat_terms(self, fetch):
        page = fare_html() + fare_html(
            name="Main", price=1070, seat="Free seat selection", bag="1st checked bag free",
        )
        page += '<div class="ML8Iie">Fare and baggage fees apply to your entire trip.</div>'
        fetch.return_value = [page, page]
        result = get_booking_details(self.token)
        self.assertEqual(len(result["booking_options"]), 2)
        basic, main = result["booking_options"][0], result["booking_options"][1]
        self.assertEqual(basic["price"], "$830")  # Do not invent a bag-inclusive total.
        self.assertEqual(basic["baggage"], [
            "1 free carry-on", "First checked bag costs 150 US dollars",
        ])
        self.assertEqual(basic["seat_selection"], "No seat selection")
        self.assertEqual(main["seat_selection"], "Free seat selection")
        self.assertEqual(main["baggage"][1], "1st checked bag free")
        self.assertEqual(len(result["fee_notes"]), 1)
        self.assertEqual(result["selected_flights"], self.selections)
        self.assertTrue(result["booking_url"].startswith("https://www.google.com/travel/flights/"))

    @patch("booking_details._fetch_booking_pages")
    def test_seller_without_fare_details_stays_unknown(self, fetch):
        fetch.return_value = [
            '<button aria-label="Continue to book with Delta airline for 830 US dollars"/>',
        ]
        fare = get_booking_details(self.token)["booking_options"][0]
        self.assertFalse(fare["details_available"])
        self.assertIsNone(fare["seat_selection"])
        self.assertIsNone(fare["fare_type"])
        self.assertEqual(fare["baggage"], [])

    @patch("booking_details._fetch_booking_pages", return_value=["<html>Getting prices</html>"])
    def test_unavailable_fares_are_an_error(self, _fetch):
        with self.assertRaisesRegex(ValueError, "No readable booking fares"):
            get_booking_details(self.token)

    @patch("booking_details._fetch_booking_pages")
    def test_round_trip_requires_a_selected_return_before_browser(self, fetch):
        self.request.return_date = "2026-12-10"
        token = encode_selection(self.request, self.selections)
        with self.assertRaisesRegex(ValueError, "Select a return flight"):
            get_booking_details(token)
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
