# Flights MCP

Search Google Flights from a command-line script or an MCP client such as Codex or Claude Desktop. This fork of [Anmoldureha/flights-skill](https://github.com/Anmoldureha/flights-skill) uses [uv](https://docs.astral.sh/uv/) to manage Python and dependencies.

The server uses the unofficial [fast-flights](https://github.com/AWeirdDev/flights) scraper. No API key is required. Searches are one-way, economy, for one adult; the MCP server returns up to 10 flights. Both the CLI and MCP explicitly request US dollars and include `"currency": "USD"` in the response. Scraping can fail when Google changes its pages or blocks requests. Searches use v3's direct Google Flights fetcher; the old third-party Playwright fallback is no longer used.

## Installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then clone this fork:

```sh
git clone git@github.com:gerin98/flights-skill.git
cd flights-skill
uv sync --locked --managed-python
```

uv downloads Python 3.12 if needed and creates `.venv` in the repository. You do not need to install Python separately, activate the environment, or run pip manually.

The environment is defined by:

- `.python-version`: the project's Python version, 3.12.
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
```

Use a future departure date when trying the example. The script prints JSON with `currency` and a `flights` array. Each flight includes `name`, `price`, `duration`, `duration_minutes`, `departure`, `arrival`, `stops`, and a `segments` array with each leg's airport codes, times, and `duration_minutes`.

### v3 response changes

- Prices are USD strings, such as `"$364"`. A missing fare is `null`.
- The old `current_price` low/typical/high assessment has been removed. The fare remains in each flight's `price` field.
- Departure and arrival are ISO-formatted local airport times, such as `"2026-12-02T00:47"`. They do not include UTC offsets.
- `duration` and `duration_minutes` describe the full itinerary, including layovers, for both nonstop and connecting flights. The adapter preserves Google's total duration from the same structured response because the v3 model drops it. This avoids deriving elapsed time from airport-local timestamps without UTC offsets. Each segment's `duration_minutes` describes only that flight leg.
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

The MCP tool is `search_flights`:

```json
{
  "origin": "JFK",
  "destination": "SFO",
  "date": "2026-12-01"
}
```

For example, ask your MCP client to find one-way flights from JFK to SFO on a future date.

### OpenClaw / script integration

Run from this checkout, or use an absolute path with `--directory`:

```sh
uv run --directory /absolute/path/to/flights-skill --locked --managed-python python search.py JFK SFO 2026-12-01
```

Map your integration's origin, destination, and date arguments to the script's three positional arguments.

## Development and testing

Run the existing unit tests:

```sh
uv run --locked --managed-python python -m unittest discover -s tests
```

These tests cover query currency, v3 parsing and result conversion, overnight connections, full journey durations, missing fares, errors, and best/remaining-flight groups using synthetic responses. They do not verify that Google Flights is reachable or that its current pages can be parsed. After dependency changes, also start the MCP client and perform a real search. The total-duration adapter relies on the structured payload format used by the pinned parser; check both together when updating the upstream revision.

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
