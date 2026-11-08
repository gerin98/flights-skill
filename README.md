# Flights MCP

Search Google Flights from a command-line script or an MCP client such as Codex or Claude Desktop. This fork of [Anmoldureha/flights-skill](https://github.com/Anmoldureha/flights-skill) uses [uv](https://docs.astral.sh/uv/) to manage Python and dependencies.

The server uses the unofficial [fast-flights](https://github.com/AWeirdDev/flights) scraper. No API key is required. Search one-way or round-trip flights with passenger counts, cabin preferences, and baggage filters. Defaults remain one-way, economy, one adult, and no baggage filter; the MCP server returns up to 10 flight options. Both the CLI and MCP explicitly request US dollars and include `"currency": "USD"` in the response. Scraping can fail when Google changes its pages or blocks requests. Searches use v3's direct Google Flights fetcher; the old third-party Playwright fallback is no longer used.

## Installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then clone this fork:

```sh
git clone git@github.com:gerin98/flights-skill.git
cd flights-skill
uv sync --locked --managed-python
```

uv downloads Python 3.15 if needed and creates `.venv` in the repository. You do not need to install Python separately, activate the environment, or run pip manually.

Searches and matching returns use direct HTTP requests. The optional fare-details lookup uses Playwright to read Google's dynamically loaded booking page in a fresh browser session. It uses an installed Google Chrome, or Playwright Chromium if Chrome is unavailable. To install Chromium:

```sh
uv run --locked --managed-python playwright install chromium
```

No API key or paid scraping service is required. The browser does not use your personal Chrome profile and never clicks airline checkout or booking buttons.

The environment is defined by:

- `.python-version`: the project's Python version, 3.15.
- `pyproject.toml`: project metadata and direct dependencies.
- `uv.lock`: resolved dependency versions, registry package hashes, and Git revisions; commit this file.

The server uses the fast-flights v3 API. The latest published release is 3.1.0, but its parser omits Google's best-flight group and cannot handle missing fares. This project therefore pins the upstream v3 source at [`4261437c506b228d20969910178a19e6d1bd2592`](https://github.com/AWeirdDev/flights/commit/4261437c506b228d20969910178a19e6d1bd2592), which includes those fixes, through `[tool.uv.sources]`. This is a fixed source revision, not a moving branch or the PyPI 3.1.0 wheel. Git must be installed to fetch it.

`primp==2.0.1` supplies the Chrome 145 profile used by this v3 fetcher. Upgrading either dependency requires compatibility checks. `--locked` stops if the manifest and lockfile disagree rather than silently changing the lockfile.

If you already have the manually created `.venv`, run the same `uv sync` command to reconcile it with the project's lockfile. The repository now contains the launcher; no separate setup script is needed.

## Command-line usage

Run from the repository directory:

```sh
# Arguments: origin airport, destination airport, departure date (YYYY-MM-DD).
uv run --locked --managed-python python search.py JFK SFO 2026-12-01

# Round-trip search for two adults and a child in premium economy, with bag filters.
uv run --locked --managed-python python search.py JFK CDG 2027-05-01 \
  --return-date 2027-05-10 --adults 2 --children 1 \
  --cabin premium-economy --carry-on-bags 1 --checked-bags 1
```

Use future dates when trying the examples. Run `python search.py --help` through `uv run` for all flags. The CLI accepts the same options as the MCP tool, with hyphens in flag names (for example, `--infants-on-lap`). Invalid arguments produce a JSON error.

The initial response includes `currency`, `current_price`, and a `flights` array, plus `search` (the normalized input options), `search_url`, `price_scope`, `result_scope`, and explanatory `notes`. Each flight includes `name`, `price`, `duration`, `duration_minutes`, `departure`, `arrival`, `stops`, and a `segments` array with each leg's airport codes, times, duration, airline code, and flight number when available.

Round-trip outbound results contain `return_search_token` and `return_search_url`; one-way results contain `booking_token` and `booking_url`. Continue via the CLI using the corresponding token unchanged:

```sh
uv run --locked --managed-python python search.py returns 'RETURN_SEARCH_TOKEN'
uv run --locked --managed-python python search.py fares 'BOOKING_TOKEN'
```

Continuation tokens encode the search and selected flight identities. They are not credentials or reservations. If Google omits identifiers, the result has `selection_unavailable: true` and can still be explored using `search_url`.

### Round trips, passenger totals, and baggage

Providing `return_date` requests a round trip; omitting it requests one-way. The initial round-trip search shows outbound options with round-trip fares. Call `search_return_flights` with an outbound's `return_search_token` to retrieve matching return flights. Its response includes `selected_outbound` and return options whose prices each cover that specific pair for the entire passenger group. It confirms the outbound identity in Google's response and never adds unrelated one-way fares together.

Use a return option's `booking_token` with `get_booking_details` to inspect the exact itinerary's fare tiers, bag charges/allowances, and seat-selection terms reported by Google. The result includes `booking_options`, `baggage_policies`, `fee_notes`, and a `booking_url` with both flights selected for manual booking. For one-way flights, use the initial result's `booking_token` directly.

- `price_scope` is `one-way_all_passengers` or `round-trip_all_passengers`. Fares are Google's quoted totals for the requested passenger group; do not multiply them by the passenger count again.
- `result_scope` is `one_way_itineraries`, `outbound_options`, or `return_options`. Durations, timestamps, and segments describe the returned direction; matching return responses include the outbound separately as `selected_outbound`, without a second price to add.
- `carry_on_bags` and `checked_bags` are forwarded as search filters. Filter inclusion alone is unverified. `get_booking_details` reads fare-specific baggage text, such as a first checked-bag charge or an included allowance, when Google publishes it. Bag charges are preserved as reported rather than automatically added to the group fare, since fee scope and passenger allowances can differ. Google's [bag-fee documentation](https://support.google.com/travel/answer/9074247?hl=en) describes these as estimates.
- Fare details report seat-selection terms such as free selection, selection for a fee, or no selection. A missing detail is unknown, not free. Exact prices for a particular seat may still require the airline's seat map; the tool does not choose seats or make bookings.
- `cabin` requests economy, premium economy, business, or first. Google can include mixed-cabin connections. The current search parser does not expose each segment's cabin, so confirm it on Google or with the airline.

### v3 response changes

- Prices are USD strings, such as `"$364"`. A missing fare is `null`.
- `current_price` is Google's assessment for the overall search: `"low"`, `"typical"`, or `"high"`. It is extracted from `span.gOatQ` in the same HTML response, without another request, because the v3 model omits it. Missing, empty, or unrecognized assessments return `null`, including when Google changes the selector. Individual fares remain in each flight's `price` field.
- Departure and arrival are ISO-formatted local airport times, such as `"2026-12-02T00:47"`. They do not include UTC offsets.
- `duration` and `duration_minutes` describe the returned journey, including layovers, for both nonstop and connecting flights. For round trips this is one direction, not the sum of both. The adapter preserves Google's total duration from the same structured response because the v3 model drops it. This avoids deriving elapsed time from airport-local timestamps without UTC offsets. Each segment's `duration_minutes` describes only that flight leg.
- The MCP returns up to 10 itineraries in upstream order; the CLI returns all available itineraries. The parser includes both Google's best-flight and remaining-flight groups.

## MCP setup

`launch-mcp.sh` changes to the repository directory, uses `uv run` to synchronize the locked environment, and starts the server with unbuffered stdout. The server uses stdout for MCP messages and writes diagnostics to `mcp_server.log` in the checkout.

### Codex

Run from the repository directory:

```sh
codex mcp add flights --env "UV_BIN=$(command -v uv)" -- /bin/sh "$PWD/launch-mcp.sh"
```

`UV_BIN` records the absolute uv path so the launcher also works when Codex's GUI environment does not include uv on `PATH`. Restart Codex after registration.

If an existing `flights` entry already launches this checkout's `launch-mcp.sh`, keep it and restart Codex after updating the files. If uv is not on the client's `PATH`, set `UV_BIN` in that server's environment to the output of `command -v uv`.

### Claude Desktop

Add this server to `claude_desktop_config.json`, substituting your absolute repository and uv paths:

```json
{
  "mcpServers": {
    "flights": {
      "command": "/bin/sh",
      "args": ["/absolute/path/to/flights-skill/launch-mcp.sh"],
      "env": {
        "UV_BIN": "/absolute/path/to/uv"
      }
    }
  }
}
```

Restart Claude Desktop after saving the configuration.

### Tool interface

Start with `search_flights`:

```json
{
  "origin": "JFK",
  "destination": "SFO",
  "date": "2026-12-01"
}
```

For example, ask your MCP client to find one-way flights from JFK to SFO on a future date.

The three MCP tools form a read-only selection flow:

| Tool | Input | Result |
| --- | --- | --- |
| `search_flights` | Search options below | One-way itineraries or round-trip outbound options. |
| `search_return_flights` | `selection_token`: an outbound's `return_search_token` | Matching return options, selected outbound details, combined fares, and booking tokens/URLs. |
| `get_booking_details` | `booking_token`: a one-way or return option's token | Fare tiers with published bag/seat terms and a link to finish booking manually. |

`get_booking_details` requires Chrome or Playwright Chromium. Missing or unrecognized fare data produces an error rather than being treated as a free allowance. No airline checkout or payment action is performed.

Optional arguments:

| Argument | Default | Meaning |
| --- | --- | --- |
| `return_date` | omitted | Round-trip return date, on or after departure, in `YYYY-MM-DD` format. |
| `cabin` | `economy` | `economy`, `premium-economy`, `business`, or `first`. |
| `adults` | `1` | Adult passengers; at least one required. |
| `children` | `0` | Children aged 2–11. |
| `infants_in_seat` | `0` | Infants under 2 occupying their own seats. |
| `infants_on_lap` | `0` | Infants under 2 on laps; no more than the adult count. |
| `carry_on_bags` | `0` | Requested carry-on bag filter, 0 or 1; fee inclusion unverified. |
| `checked_bags` | `0` | Requested checked-bag filter, 0–2; fee inclusion unverified. |

At most 9 passengers are supported, including infants. Counts must be integers; unsupported options and invalid dates are rejected before a network request. Airport codes are normalized to uppercase.

Example round-trip tool arguments:

```json
{
  "origin": "JFK",
  "destination": "CDG",
  "date": "2027-05-01",
  "return_date": "2027-05-10",
  "adults": 2,
  "children": 1,
  "cabin": "premium-economy",
  "carry_on_bags": 1,
  "checked_bags": 1
}
```

### OpenClaw / script integration

Run from this checkout, or use an absolute path with `--directory`:

```sh
uv run --directory /absolute/path/to/flights-skill --locked --managed-python python search.py JFK SFO 2026-12-01
```

Map your integration's origin, destination, and date arguments to the script's three positional arguments, and any optional arguments to their corresponding flags.

## Development and testing

Install the locked environment, including the Pylint development dependency, and run the checks:

```sh
uv sync --locked --managed-python --dev
git ls-files -z '*.py' | xargs -0 uv run --locked --managed-python pylint
uv run --locked --managed-python python -m unittest discover -s tests -v
```

The [CI workflow](.github/workflows/ci.yml) runs these lint and test commands on pushes and pull requests using Ubuntu and Python 3.15 from `.python-version`. It uses the official `astral-sh/setup-uv` action, a pinned uv version, and `uv.lock` for reproducible dependencies. Pylint checks all tracked Python files; add new files to Git before running that command locally. CI uses synthetic flight responses and fare HTML, without live searches or launching a browser.

Pylint configuration is in `pyproject.toml`. It allows inspection of the compiled `selectolax.lexbor` module; intentional exceptions, such as broad error handling at the CLI/MCP boundary, are documented beside the code. Use `uv add --dev PACKAGE` for development tools.

These tests cover query currency, round-trip routing, passenger/cabin/baggage options, input validation, v3 parsing and result conversion, overnight connections, full journey durations, price assessments and their absence, missing fares, errors, and best/remaining-flight groups using synthetic responses. They verify that CLI and MCP options reach the upstream query and that group fares are not multiplied again. They do not verify that Google Flights is reachable or that its current pages can be parsed. After dependency changes, also start the MCP client and perform a real search. The total-duration adapter relies on the structured payload format used by the pinned parser; check both together when updating the upstream revision.

Continuation tests cover selected-flight encoding, token validation, matching the confirmed outbound, and preserving combined fares. Fare tests cover published baggage/seat terms, missing details, and preventing a round-trip fare lookup before a return is selected. Selected-flight protobuf fields and booking-page selectors are unofficial Google formats; live-check the full selection flow after upstream changes.

Use `uv add PACKAGE` to add a dependency and update both `pyproject.toml` and `uv.lock`. Review and commit those files together. `uv lock --upgrade` does not advance the pinned fast-flights Git revision. To update other dependencies within the pinned direct requirements:

```sh
uv lock --upgrade
uv sync --locked --managed-python
uv run --locked --managed-python python -m unittest discover -s tests
```

Keep `.venv`, logs, and local backups out of Git. For personal forks, configure commit identity and signing with repository-local Git settings.

## Credits

Original MCP wrapper: [Anmoldureha/flights-skill](https://github.com/Anmoldureha/flights-skill).

Flight search library: [AWeirdDev/flights](https://github.com/AWeirdDev/flights).
