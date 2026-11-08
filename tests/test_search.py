"""CLI argument and error-output tests."""

# Test method names describe the behavior without repetitive docstrings.
# pylint: disable=missing-function-docstring
# Each CLI test keeps its short stdout/argv setup visible in the test itself.
# pylint: disable=duplicate-code

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# Also allow running this file directly, as documented by the original repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import search  # pylint: disable=wrong-import-position


class SearchCliTests(unittest.TestCase):
    """Verify that CLI failures remain machine-readable."""
    def test_missing_args(self):
        output = StringIO()
        with patch.object(sys, "argv", ["search.py"]), redirect_stdout(output):
            search.main()
        self.assertIn("Usage", json.loads(output.getvalue())["error"])

    @patch("search.search_flights", side_effect=RuntimeError("Search unavailable"))
    def test_error_is_json(self, _fetch):
        output = StringIO()
        with (
            patch.object(sys, "argv", ["search.py", "JFK", "SFO", "2026-12-01"]),
            redirect_stdout(output),
        ):
            search.main()
        self.assertEqual(json.loads(output.getvalue()), {"error": "Search unavailable"})


if __name__ == "__main__":
    unittest.main()
