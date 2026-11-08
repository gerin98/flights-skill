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

Round-trip results are **outbound options with round-trip fares**, not complete return itineraries. `result_scope` is `outbound_options`; `price_scope` is `round-trip_all_passengers`. Direct the user to `search_url` to select the outbound and return flights and confirm the final fare. Do not invent return segments or add two unrelated one-way fares as a round-trip quote.

Departure and arrival use ISO-formatted airport-local times without UTC offsets. Each flight's `duration` and `duration_minutes` include the returned journey and its layovers; for round trips, these describe only the outbound journey. Its `segments` contain individual flying times, which exclude layovers. The top-level `current_price` is Google's assessment for the overall search (`"low"`, `"typical"`, or `"high"`), or `null` when unavailable. It is not an assessment of each individual flight.

Baggage options are forwarded to Google, but fee inclusion and allowances are unverified, particularly for checked bags. Cabin class is a search preference: mixed-cabin connections may appear, and each segment's cabin needs confirmation. Specific seat selection and seat-selection fees are not supported. Explain these limits when discussing totals rather than presenting them as verified all-inclusive prices.

## Script integration

```sh
uv run --directory /absolute/path/to/flights-skill --locked --managed-python python search.py JFK SFO 2026-12-01

uv run --directory /absolute/path/to/flights-skill --locked --managed-python python search.py JFK CDG 2027-05-01 \
  --return-date 2027-05-10 --adults 2 --cabin premium-economy --checked-bags 1
```

Replace the three positional arguments with the origin, destination, and date. Optional CLI flags use hyphens where tool argument names use underscores. No environment activation is needed.
