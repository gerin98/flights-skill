"""Read fare-specific baggage and seat information without entering airline checkout."""

import re

from playwright.sync_api import Error as BrowserError, sync_playwright
from selectolax.lexbor import LexborHTMLParser

from flight_selection import decode_selection, selected_query


BOOK_BUTTON = 'button[aria-label^="Continue to book with "]'


def _fetch_booking_pages(url):
    """Render Google's fare cards in an isolated browser; never click Continue or book."""
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
        except BrowserError:
            try:
                browser = playwright.chromium.launch(headless=True)
            except BrowserError as error:
                raise RuntimeError(
                    "Fare details need Chrome or Playwright Chromium. Install Chrome or run "
                    "'uv run playwright install chromium', then retry."
                ) from error
        try:
            page = browser.new_page(locale="en-US")
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector(BOOK_BUTTON, timeout=20000)
            pages = [page.content()]
            # Reveal fare tiers within Google only. No airline checkout buttons are clicked.
            for _ in range(5):
                options = page.get_by_role("button", name="View options", exact=True)
                if not options.count():
                    break
                try:
                    options.first.click(timeout=2000)
                    pages.append(page.content())
                except BrowserError:
                    break  # Return the readable fares if another provider cannot be expanded.
            return pages
        except BrowserError as error:
            raise RuntimeError(
                "Google did not load booking fares. Open the booking_url manually or retry later."
            ) from error
        finally:
            browser.close()


def _fare_card(button):
    node = button.parent
    while node is not None:
        if len(node.css(BOOK_BUTTON)) > 1:
            break
        if node.css_first("h3.DllrY") is not None:
            return node
        node = node.parent
    return None


def _baggage_text(item):
    # The accessible label avoids duplicating the visible version of the same fee.
    accessible = item.css_first(".HeMQ4")
    return (accessible or item).text(separator=" ", strip=True)


def _parse_booking_page(html):
    parser = LexborHTMLParser(html)
    fares = []
    for button in parser.css(BOOK_BUTTON):
        label = button.attributes.get("aria-label", "")
        match = re.fullmatch(r"Continue to book with (.+) for ([\d,.]+) US dollars", label)
        if match is None:
            continue
        seller, amount = match.groups()
        card = _fare_card(button)
        fare_type, baggage, features = None, [], []
        if card is not None:
            fare_type = card.css_first("h3.DllrY").text(strip=True)
            seller = seller.removesuffix(", " + fare_type)
            baggage = [_baggage_text(item) for item in card.css('ul[jsname="vNB5le"] li')]
            features = [item.text(strip=True) for item in card.css(".hEkLUb")]
        seat_selection = next((s for s in features if "seat selection" in s.lower()), None)
        fares.append({
            "book_with": seller.removesuffix(" airline"),
            "fare_type": fare_type, "price": "$" + amount,
            "baggage": baggage, "seat_selection": seat_selection,
            "features": features, "details_available": card is not None,
        })
    policies = [{"name": a.text(strip=True), "url": a.attributes["href"]}
                for a in parser.css('a[href]') if "bag policy" in a.text().lower()]
    fee_notes = [node.text(separator=" ", strip=True) for node in parser.css("div.ML8Iie")
                 if "fees" in node.text().lower()]
    return fares, policies, fee_notes


def get_booking_details(booking_token: str) -> dict:
    """Return Google's fare tiers for an exact selected itinerary, with a manual booking link."""
    request, selections = decode_selection(booking_token)
    if len(selections) != (2 if request.return_date else 1):
        raise ValueError("Select a return flight first, then use its booking_token")
    url = selected_query(request, selections).url()
    fares, policies, fee_notes = {}, {}, set()
    for html in _fetch_booking_pages(url):
        page_fares, page_policies, page_notes = _parse_booking_page(html)
        for fare in page_fares:
            fares[(fare["book_with"], fare["fare_type"], fare["price"])] = fare
        for policy in page_policies:
            policies[policy["url"]] = policy
        fee_notes.update(page_notes)
    if not fares:
        raise ValueError("No readable booking fares returned; open booking_url manually")
    return {
        "source": "Google Flights", "currency": "USD", "search": request.metadata(),
        "selected_flights": selections, "booking_url": url,
        "price_scope": f"{request.trip_type}_all_passengers",
        "booking_options": list(fares.values()), "baggage_policies": list(policies.values()),
        "fee_notes": sorted(fee_notes),
        "notes": [
            "Fare prices and baggage/seat terms are reported by Google for the selected flights. "
            "Baggage amounts are kept as reported; they have not been added to fare totals.",
            "A missing bag or seat detail is unknown, not free. Exact prices for individual "
            "seats may require the airline seat map. Confirm final availability at checkout.",
            "Open booking_url to choose the fare and book manually. No booking was made.",
        ],
    }
