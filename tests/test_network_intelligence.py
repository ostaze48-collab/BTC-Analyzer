import unittest

from app.network_intelligence import summarize_coinmetrics, summarize_mempool, network_shadow_summary


class NetworkIntelligenceTests(unittest.TestCase):
    def test_mempool_summary(self):
        mempool = {"count": 50000, "vsize": 120_000_000, "total_fee": 25_000_000}
        hashrate = {
            "currentHashrate": 110.0,
            "currentDifficulty": 50.0,
            "hashrates": [{"avgHashrate": 100.0}, {"avgHashrate": 105.0}],
        }
        difficulty = {"difficultyChange": 3.2}
        fees = {"fastestFee": 8, "hourFee": 3, "minimumFee": 1}
        result = summarize_mempool(mempool, hashrate, difficulty, fees)
        self.assertTrue(result["available"])
        self.assertEqual(result["mempool"]["tx_count"], 50000)
        self.assertAlmostEqual(result["mempool"]["vsize_mb"], 120.0)
        self.assertIn("hashrate_vs_30d_mean_pct", result["mining"])
        self.assertEqual(result["fees"]["fastestFee"], 8.0)

    def test_coinmetrics_changes(self):
        rows = []
        for i in range(35):
            rows.append({
                "time": f"2026-09-{(i%30)+1:02d}",
                "AdrActCnt": str(1000 + i * 10),
                "TxCnt": str(2000 + i * 20),
                "IssTotNtv": "450",
                "HashRate": str(100 + i),
                "CapMrktCurUSD": str(1_000_000 + i * 10000),
            })
        result = summarize_coinmetrics(rows)
        self.assertTrue(result["available"])
        self.assertIn("AdrActCnt", result["metrics"])
        self.assertIsNotNone(result["metrics"]["AdrActCnt"]["change_30d_pct"])

    def test_network_context_has_zero_master_weight(self):
        mp = summarize_mempool(
            {"count": 10000, "vsize": 10_000_000, "total_fee": 1000},
            {"currentHashrate": 120.0, "hashrates": [{"avgHashrate": 100.0}]},
            {}, {},
        )
        cm = summarize_coinmetrics([
            {"time":"2026-01-01","AdrActCnt":"100","TxCnt":"200","HashRate":"100","CapMrktCurUSD":"1000"},
            {"time":"2026-02-01","AdrActCnt":"120","TxCnt":"230","HashRate":"110","CapMrktCurUSD":"1200"},
        ])
        shadow = network_shadow_summary(mp, cm)
        self.assertEqual(shadow["mode"], "SHADOW_ONLY")
        self.assertEqual(shadow["weight_in_master"], 0.0)


if __name__ == "__main__":
    unittest.main()
