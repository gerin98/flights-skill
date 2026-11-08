"""Serve Google Flights searches over the MCP stdio JSON-RPC transport."""

import sys
import json
import logging
from flight_search import search_flights
from search_options import SEARCH_SCHEMA

# Configure logging to file since stdout is used for protocol
logging.basicConfig(filename='mcp_server.log', level=logging.INFO)

def search_logic(arguments):
    """Search up to ten itineraries and log failures before propagating them."""
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be an object")
    unknown = set(arguments) - set(SEARCH_SCHEMA["properties"])
    if unknown:
        raise ValueError(f"Unsupported search options: {', '.join(sorted(unknown))}")
    logging.info("Searching: %s", arguments)
    try:
        return search_flights(**arguments, limit=10)
    except Exception:
        logging.exception("Search failed")
        raise

# Each supported JSON-RPC method returns its own protocol response.
# pylint: disable-next=too-many-return-statements
def handle_request(req):
    """Dispatch one request, returning no response for initialization notifications."""
    method = req.get("method")
    msg_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": { "tools": {} },
                "serverInfo": { "name": "flights-skill", "version": "1.0.0" }
            }
        }

    if method == "notifications/initialized":
        # Client confirming initialization. No response needed.
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [{
                    "name": "search_flights",
                    "description": (
                        "Search Google Flights with optional return date, passenger counts, "
                        "cabin class, and baggage filters. Defaults: one-way, one adult, economy. "
                        "Prices are USD totals for all requested passengers. Round-trip results "
                        "are outbound options with round-trip fares; choose the return at "
                        "search_url. Durations cover the returned journey including layovers. "
                        "Bag fees and each segment's cabin require confirmation. "
                        "Specific seat selection is not supported. Times are airport-local."
                    ),
                    "inputSchema": SEARCH_SCHEMA,
                }]
            }
        }

    if method == "tools/call":
        params = req.get("params", {})
        if params.get("name") == "search_flights":
            args = params.get("arguments", {})
            try:
                data = search_logic(args)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{ "type": "text", "text": json.dumps(data, indent=2) }]
                    }
                }
            # Convert upstream failures to JSON-RPC errors at the transport boundary.
            except Exception as e:  # pylint: disable=broad-exception-caught
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": { "code": -32000, "message": str(e) }
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": { "code": -32601, "message": "Method not found" }
            }

    # Default for unknown methods (ping etc)
    # MCP requires ignoring notifications, but replying error to requests
    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": { "code": -32601, "message": "Method not found or not implemented" }
        }
    return None

def main():
    """Read requests until EOF, keeping stdout reserved for protocol responses."""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue

            res = handle_request(req)
            if res:
                print(json.dumps(res))
                sys.stdout.flush()

        # A malformed request must not terminate the long-running MCP transport.
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.critical("Critical Loop Error: %s", e)

if __name__ == "__main__":
    main()
