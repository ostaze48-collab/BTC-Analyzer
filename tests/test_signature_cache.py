import unittest

from app.config import settings
from app.historical_analogs import (
    _DEEP_CACHE_MIN_BARS,
    _HORIZON_BY_BRAIN,
    _history_revision,
    build_signature_memory,
)


def candles(n: int, step: int = 300):
    out = []
    price = 100.0
    for i in range(n):
        price += 0.03 + ((i % 9) - 4) * 0.004
        t = 1_700_000_000 + i * step
        out.append({
            "time": t, "close_time": t,
            "open": price - 0.05, "high": price + 0.2,
            "low": price - 0.2, "close": price, "volume": 100 + (i % 13),
            "closed": True,
        })
    return out


class SignatureCacheTests(unittest.TestCase):
    def test_cache_requires_deep_history_threshold(self):
        self.assertGreater(_DEEP_CACHE_MIN_BARS, 500)

    def test_revision_does_not_change_for_one_same_day_append(self):
        base = candles(800, 60)
        history1 = {"5m": list(base)}
        history2 = {"5m": list(base) + [{**base[-1], "time": base[-1]["time"] + 60, "close_time": base[-1]["close_time"] + 60}]}
        self.assertEqual(
            _history_revision(history1, "SCALP", "5m"),
            _history_revision(history2, "SCALP", "5m"),
        )

    def test_signature_memory_is_bounded_and_has_complete_future_horizon(self):
        base = candles(820, 300)
        history = {tf: list(base) for tf in settings.intervals}
        memory, meta = build_signature_memory(history, "SCALP", "5m", max_candidates=24)
        self.assertGreater(len(memory), 0)
        self.assertLessEqual(len(memory), 24)
        horizon = _HORIZON_BY_BRAIN["SCALP"]
        for row in memory:
            self.assertLess(int(row["idx"]) + horizon, len(history["5m"]))
        self.assertEqual(meta["target_candidates"], 24)


if __name__ == "__main__":
    unittest.main()
