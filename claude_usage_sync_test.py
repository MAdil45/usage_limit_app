import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from claude_usage_sync import latest_sample, normalize, save


class ClaudeDesktopHistoryTests(unittest.TestCase):
    def test_reads_latest_valid_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.json"
            history.write_text(json.dumps({"samples": [
                {"t": 1000, "u": {"fh": 3, "sd": 8}},
                {"t": 2000, "u": {"fh": 5, "sd": 13}},
            ]}))
            windows, sampled_at = normalize(latest_sample(history))
            self.assertEqual(windows["5-hour"]["used"], 5)
            self.assertEqual(windows["Weekly"]["used"], 13)
            self.assertEqual(sampled_at, datetime.fromtimestamp(2, timezone.utc))

    def test_does_not_replace_newer_browser_data(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "usage.json"
            state.write_text(json.dumps({"providers": {"Claude": {
                "5-hour": {"used": 9, "updated_at": "2026-11-10T12:00:00+00:00"},
                "Weekly": {"used": 20, "updated_at": "2026-11-10T12:00:00+00:00"},
            }}}))
            changed = save(
                {"5-hour": {"used": 4}, "Weekly": {"used": 10}},
                datetime(2026, 11, 10, 11, tzinfo=timezone.utc),
                state,
            )
            self.assertFalse(changed)
            data = json.loads(state.read_text())
            self.assertEqual(data["providers"]["Claude"]["5-hour"]["used"], 9)


if __name__ == "__main__":
    unittest.main()
