from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# Also allow running this file directly, as documented by the original repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import search


class SearchCliTests(unittest.TestCase):
    def test_missing_args(self):
        output = StringIO()
        with patch.object(sys, "argv", ["search.py"]), redirect_stdout(output):
            search.main()
        self.assertIn("Usage", json.loads(output.getvalue())["error"])

    @patch("search.search_flights", side_effect=RuntimeError("Search unavailable"))
    def test_error_is_json(self, fetch):
        output = StringIO()
        with patch.object(sys, "argv", ["search.py", "JFK", "SFO", "2026-12-01"]), redirect_stdout(output):
            search.main()
        self.assertEqual(json.loads(output.getvalue()), {"error": "Search unavailable"})


if __name__ == "__main__":
    unittest.main()
