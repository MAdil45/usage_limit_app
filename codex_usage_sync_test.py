import unittest

from codex_usage_sync import classify_windows


class RateLimitParsingTests(unittest.TestCase):
    def test_classifies_reordered_windows_by_duration(self):
        result = {"rateLimits": {
            "primary": {"usedPercent": 33, "windowDurationMins": 10080, "resetsAt": 1800000000},
            "secondary": {"usedPercent": 23, "windowDurationMins": 300, "resetsAt": 1799400000},
        }}
        windows = classify_windows(result)
        self.assertEqual(windows["5-hour"]["used"], 23)
        self.assertEqual(windows["Weekly"]["used"], 33)

    def test_supports_weekly_only_plans(self):
        result = {"rateLimitsByLimitId": {"codex": {
            "primary": {"usedPercent": 41, "windowDurationMins": 10080, "resetsAt": 1800000000},
            "secondary": None,
        }}}
        windows = classify_windows(result)
        self.assertTrue(windows["5-hour"]["unavailable"])
        self.assertEqual(windows["Weekly"]["used"], 41)


if __name__ == "__main__":
    unittest.main()
