"""Serve Google Flights searches over the MCP stdio JSON-RPC transport."""

import sys
import json
import logging
from booking_details import get_booking_details
from flight_search import search_flights, search_return_flights
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


def _call_tool(name, arguments):
    if name == "search_flights":
        return search_logic(arguments)
    token_name = "selection_token" if name == "search_return_flights" else "booking_token"
    if not isinstance(arguments, dict) or set(arguments) != {token_name}:
        raise ValueError(f"Provide only {token_name} from a previous flight result")
    if name == "search_return_flights":
        return search_return_flights(arguments[token_name], limit=10)
    return get_booking_details(arguments[token_name])

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
                        "search_url, or call search_return_flights with a return_search_token. "
                        "For a complete selection, use get_booking_details with its booking_token "
                        "to read fare-specific baggage and seat-selection terms. "
                        "Durations include layovers. Times are airport-local."
                    ),
                    "inputSchema": SEARCH_SCHEMA,
                }, {
                    "name": "search_return_flights",
                    "description": (
                        "Get matching return flights for a specific outbound. Each price covers "
                        "both selected_outbound and that return for all requested passengers. "
                        "Use a return's booking_token with get_booking_details for fare options, "
                        "or its booking_url to book manually."
                    ),
                    "inputSchema": {
                        "type": "object", "additionalProperties": False,
                        "properties": {"selection_token": {
                            "type": "string", "description": "An outbound's return_search_token",
                        }},
                        "required": ["selection_token"],
                    },
                }, {
                    "name": "get_booking_details",
                    "description": (
                        "Read Google Flights fare tiers, baggage charges/allowances, and "
                        "seat-selection terms for selected flights using an isolated browser. "
                        "Missing fees are unknown, not zero. Exact individual seat prices may "
                        "require the airline seat map. Returns booking_url for manual booking; "
                        "does not book or enter airline checkout."
                    ),
                    "inputSchema": {
                        "type": "object", "additionalProperties": False,
                        "properties": {"booking_token": {
                            "type": "string",
                            "description": "A booking_token from a one-way or return-flight result",
                        }},
                        "required": ["booking_token"],
                    },
                }]
            }
        }

    if method == "tools/call":
        params = req.get("params", {})
        if params.get("name") in {"search_flights", "search_return_flights", "get_booking_details"}:
            args = params.get("arguments", {})
            try:
                data = _call_tool(params["name"], args)
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
