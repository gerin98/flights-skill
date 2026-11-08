"""Print one-way or round-trip Google Flights search results as JSON."""

import argparse
import json
from flight_search import search_flights
from search_options import SEARCH_PROPERTIES


class JsonArgumentParser(argparse.ArgumentParser):
    """Keep invalid CLI arguments in the same JSON error format as search failures."""

    def error(self, message):
        raise ValueError(f"Usage: {self.format_usage().removeprefix('usage: ').strip()}; {message}")


def _arguments():
    parser = JsonArgumentParser(description=__doc__)
    for name in ("origin", "destination", "date"):
        parser.add_argument(name, help=SEARCH_PROPERTIES[name]["description"])
    for name, spec in SEARCH_PROPERTIES.items():
        if name in ("origin", "destination", "date"):
            continue
        parser.add_argument(
            "--" + name.replace("_", "-"),
            type=int if spec["type"] == "integer" else str,
            default=spec.get("default"),
            choices=spec.get("enum"),
            help=spec["description"],
        )
    return vars(parser.parse_args())

def main():
    """Parse search arguments and return results or errors as JSON."""
    try:
        output = search_flights(**_arguments())
        print(json.dumps(output, indent=2))

    # Preserve machine-readable output for any upstream error at the CLI boundary.
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
