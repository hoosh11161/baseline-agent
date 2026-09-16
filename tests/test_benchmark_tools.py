from __future__ import annotations

import unittest

from scripts.compare_benchmarks import build_comparison
from scripts.model_benchmark import summarize_models


class BenchmarkToolTests(unittest.TestCase):
    def test_model_summary_uses_verified_episodes(self) -> None:
        episodes = [
            {
                "task_type": "npc",
                "verified": True,
                "success": True,
                "score": 1,
                "steps": 2,
                "invalid_actions": 0,
                "latency": 3,
                "tokens": 10,
                "run_metadata": {"model": "model-a"},
            },
            {
                "task_type": "npc",
                "verified": False,
                "success": False,
                "run_metadata": {"model": "model-a"},
            },
        ]
        rows = summarize_models(episodes)
        self.assertEqual(rows[0]["verified_episodes"], 1)
        self.assertEqual(rows[0]["success_rate"], 1.0)
        self.assertEqual(rows[0]["status"], "VERIFIED")

    def test_unverified_comparison_never_claims_improvement(self) -> None:
        payload = {"status": "NOT_VERIFIED", "summary": []}
        comparison = build_comparison(payload, payload)
        self.assertIn("REAL_ENV_NOT_AVAILABLE", comparison)
        self.assertIn("No percentage improvement is claimed", comparison)


if __name__ == "__main__":
    unittest.main()
