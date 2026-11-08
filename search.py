"""Print one-way Google Flights search results as JSON."""

import sys
import json
from flight_search import search_flights

def main():
    """Parse positional arguments and return results or errors as JSON."""
    try:
        if len(sys.argv) < 4:
            print(json.dumps({"error": "Usage: search.py ORIGIN DEST DATE (YYYY-MM-DD)"}))
            return

        origin = sys.argv[1]
        dest = sys.argv[2]
        date = sys.argv[3]

        output = search_flights(origin, dest, date)
        print(json.dumps(output, indent=2))

    # Preserve machine-readable output for any upstream error at the CLI boundary.
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
