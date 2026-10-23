import unittest

from app.live_shadow_target import validate_live_shadow_target


class LiveShadowTargetTests(unittest.TestCase):
    def test_entry_evidence_is_frozen_and_small_sample_never_applies(self):
        trades=[]; samples=[]
        for i in range(1,11):
            trades.append({"id":i,"mfe_pct":2.5,"exit_reason":"ADAPTIVE_TARGET_R","target_r":2.0})
            samples.append({
                "trade_id":i,"opened_at":f"2026-01-{i:02d}T00:00:00+00:00","brain":"INTRADAY","market_regime":"TREND_UP",
                "features":{
                    "schema":"learning_vector_v7",
                    "adaptive_risk_plan":{"stop_distance_pct":1.0,"target_r":2.0},
                    "historical_analogs":{"status":"READY","matches":24,"quality":"STRONG","hit_1r_pct":90,"hit_2r_pct":75,"hit_3r_pct":60,"hit_4r_pct":30,"hit_5r_pct":10},
                },
            })
        r=validate_live_shadow_target(samples,trades)
        self.assertEqual(r["status"],"INSUFFICIENT_LIVE_SHADOW_DATA")
        self.assertTrue(r["entry_evidence_frozen"])
        self.assertFalse(r["auto_apply"])
        self.assertEqual(r["weight_in_risk_engine"],0.0)

    def test_current_external_analog_data_is_not_an_input(self):
        trades=[{"id":1,"mfe_pct":1.2,"exit_reason":"STOP_LOSS","target_r":2.0}]
        sample={
            "trade_id":1,"opened_at":"2026-01-01T00:00:00+00:00","brain":"SCALP","market_regime":"RANGE",
            "features":{
                "adaptive_risk_plan":{"stop_distance_pct":1.0,"target_r":2.0},
                "historical_analogs":{"status":"READY","matches":20,"quality":"STRONG","hit_1r_pct":85,"hit_2r_pct":65,"hit_3r_pct":40,"hit_4r_pct":20,"hit_5r_pct":10},
            },
        }
        a=validate_live_shadow_target([sample],trades)
        # Mutating a separate object that represents 'today' cannot change frozen ENTRY evidence.
        current={"status":"READY","matches":999,"hit_5r_pct":100}
        current["hit_1r_pct"]=0
        b=validate_live_shadow_target([sample],trades)
        self.assertEqual(a,b)


if __name__=="__main__":
    unittest.main()
