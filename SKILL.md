# Flight Search Skill

Search one-way or round-trip flights using Google Flights through the unofficial `fast-flights` library. Defaults are one-way, economy, and one adult; passenger counts, cabin class, and baggage filters are optional.

## Setup

Install uv, then run from this repository:

```sh
uv sync --locked --managed-python
```

uv manages Python 3.15 and the project's `.venv`. The compatible dependency versions are declared in `pyproject.toml` and resolved in `uv.lock`.

## MCP tool

Launch the MCP server with `/bin/sh /absolute/path/to/flights-skill/launch-mcp.sh`. Ensure uv is on the client's `PATH`, or set `UV_BIN` to the absolute uv executable path. See README.md for Codex and Claude Desktop configuration.

The tool is `search_flights` and accepts:

- `origin`: origin airport code, such as `JFK`.
- `destination`: destination airport code, such as `SFO`.
- `date`: future departure date in `YYYY-MM-DD` format.
- `return_date` (optional): return date on or after departure; requests a round trip.
- `cabin` (optional): `economy` (default), `premium-economy`, `business`, or `first`.
- `adults`, `children`, `infants_in_seat`, `infants_on_lap` (optional): integer counts, defaulting to 1 adult and 0 others. At least one adult and at most 9 total passengers are supported; lap infants cannot exceed adults. Children are aged 2–11 and infants are under 2.
- `carry_on_bags` (optional): requested carry-on bag filter, 0 (default) or 1.
- `checked_bags` (optional): requested checked-bag filter, 0 (default), 1, or 2.

The server returns up to 10 flight options and explicitly requests USD. The response includes `currency: "USD"`; fares are in each flight's `price` field, with `null` for a missing fare. Fares are totals for the requested passenger group: do not multiply by passenger count. `search` echoes the normalized options; `price_scope`, `result_scope`, and `notes` explain what the results cover.

Initial round-trip results are outbound options. To resolve a complete trip, call `search_return_flights` with `selection_token` set to a chosen outbound's `return_search_token`. The result includes `selected_outbound` and matching return options. Each return's price already covers both directions for the requested passenger group; never add the outbound quote again.

Call `get_booking_details` with a return option's `booking_token` to read the selected pair's fare tiers. For one-way itineraries use the initial result's `booking_token` directly. Return the fare name, price, published baggage terms, and seat-selection terms when relevant. Missing information is unknown, not zero. The tool reads Google's booking page in an isolated Chrome/Chromium session and never enters airline checkout.

Include a clickable **Open Google Flights to book** link using the selected itinerary's `booking_url`. The user chooses the fare and completes booking manually. If selection identifiers are unavailable (`selection_unavailable: true`), provide `search_url` instead and explain that the pair was not resolved.

Departure and arrival use ISO-formatted airport-local times without UTC offsets. Each flight's `duration` and `duration_minutes` include that direction and its layovers. Matching return results describe the return in `flights` and the outbound in `selected_outbound`. Each journey's `segments` contain individual flying times, airline codes, and flight numbers when available. The top-level `current_price` from the initial search is Google's assessment for the overall search (`"low"`, `"typical"`, or `"high"`), or `null` when unavailable.

Baggage filters alone do not establish inclusion. Use fare-level `baggage` and `fee_notes` from `get_booking_details` to report what Google publishes. Do not automatically add bag charges to group fares without a clear passenger and journey scope. Seat-selection terms may say free, paid, or unavailable; exact prices for an individual seat can still require the airline seat map. The tool does not select seats. Mixed-cabin connections may appear, and each segment's cabin needs confirmation.

## Script integration

```sh
uv run --directory /absolute/path/to/flights-skill --locked --managed-python python search.py JFK SFO 2026-12-01

uv run --directory /absolute/path/to/flights-skill --locked --managed-python python search.py JFK CDG 2027-05-01 \
  --return-date 2027-05-10 --adults 2 --cabin premium-economy --checked-bags 1

uv run --directory /absolute/path/to/flights-skill --locked --managed-python python search.py returns 'RETURN_SEARCH_TOKEN'
uv run --directory /absolute/path/to/flights-skill --locked --managed-python python search.py fares 'BOOKING_TOKEN'
```

Replace the three positional arguments with the origin, destination, and date. Optional CLI flags use hyphens where tool argument names use underscores. No environment activation is needed.

Fare details require Google Chrome or `uv run playwright install chromium`. If Google blocks the browser or no fare data loads, use the manual booking link and report that the fare details could not be retrieved.
