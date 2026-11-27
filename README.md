# Flights MCP

Search Google Flights from the command line or an MCP client such as Codex or Claude Desktop.

## Features

- Search one-way and round-trip flights by passenger count, cabin, and baggage filters. Prices are in USD for the full passenger group.
- Select an outbound flight to find matching returns and see the total fare for each round-trip pairing.
- Look up published fare tiers, baggage allowances and fees, and seat-selection terms. Open the Google Flights link to book manually.
- Search without an API key. The unofficial scraper can break when Google changes its pages.

## Setup

Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/), then run the following. uv installs Python 3.15 and the locked dependencies.

```sh
git clone https://github.com/gerin98/flights-skill.git
cd flights-skill
uv sync --locked --managed-python
```

Fare details use Google Chrome if installed. If you need Playwright Chromium, install it with this command.

```sh
uv run --locked --managed-python playwright install chromium
```

### Command line

Use airport codes and future dates in `YYYY-MM-DD` format. Add `--return-date` for a round trip or run with `--help` for all search options.

```sh
uv run --locked --managed-python python search.py JFK SFO 2027-05-01
```

Pass an outbound's `return_search_token` to `search.py returns TOKEN` to find matching returns. Pass a one-way or return option's `booking_token` to `search.py fares TOKEN` to look up fare details. Run both commands through the same `uv run` prefix.

### Codex

From the checkout, register the MCP server and restart Codex.

```sh
codex mcp add flights --env "UV_BIN=$(command -v uv)" -- /bin/sh "$PWD/launch-mcp.sh"
```

### Claude Desktop

Add the server to `claude_desktop_config.json`, replace the example paths with your absolute paths, and restart Claude Desktop.

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

In either MCP client, ask for flights by route and date. The tools are `search_flights`, `search_return_flights`, and `get_booking_details`. See [SKILL.md](SKILL.md) for tool arguments and script examples.

## Development

```sh
uv sync --locked --managed-python --dev
git ls-files -z '*.py' | xargs -0 uv run --locked --managed-python pylint
uv run --locked --managed-python python -m unittest discover -s tests -v
```

[CI](.github/workflows/ci.yml) runs lint and tests on pushes, pull requests, and Mondays at 14:17 UTC. Tests use synthetic responses. After changes to the upstream parser or browser lookup, try a live search, select matching returns, and open fare details.

Keep `pyproject.toml` and `uv.lock` in sync. The project pins a fast-flights Git revision that includes fixes for best-flight results and missing fares.

## Credits

- Original MCP wrapper [Anmoldureha/flights-skill](https://github.com/Anmoldureha/flights-skill).
- Flight search library [AWeirdDev/flights](https://github.com/AWeirdDev/flights).
