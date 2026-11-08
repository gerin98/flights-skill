# Flight Search Skill

Search for one-way economy flights for one adult using Google Flights through the unofficial `fast-flights` library.

## Setup

Install uv, then run from this repository:

```sh
uv sync --locked --managed-python
```

uv manages Python 3.12 and the project's `.venv`. The compatible dependency versions are declared in `pyproject.toml` and resolved in `uv.lock`.

## MCP tool

Launch the MCP server with `/bin/sh /absolute/path/to/flights-skill/launch-mcp.sh`. Ensure uv is on the client's `PATH`, or set `UV_BIN` to the absolute uv executable path. See README.md for Codex and Claude Desktop configuration.

The tool is `search_flights` and accepts:

- `origin`: origin airport code, such as `JFK`.
- `destination`: destination airport code, such as `SFO`.
- `date`: future departure date in `YYYY-MM-DD` format.

The server returns up to 10 flights and explicitly requests USD. The response includes `currency: "USD"`; fares are in each flight's `price` field, with `null` for a missing fare. Departure and arrival use ISO-formatted airport-local times without UTC offsets. Each flight's `duration` and `duration_minutes` include the full journey and any layovers. Its `segments` contain individual flying times, which exclude layovers. The old `current_price` assessment is no longer returned.

## Script integration

```sh
uv run --directory /absolute/path/to/flights-skill --locked --managed-python python search.py JFK SFO 2026-12-01
```

Replace the three positional arguments with the origin, destination, and date. No environment activation is needed.
