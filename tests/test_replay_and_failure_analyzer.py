from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from arenaagent.competition.replay import replay_public_trace
from scripts.failure_analyzer import analyze_failures


class ReplayTests(unittest.TestCase):
    def test_replay_checks_visible_ids_and_repeat_loop(self) -> None:
        trace = {
            "subject": {"task_id": "replay-1", "task_type": "tidyroom", "subject": "整理"},
            "steps": [
                {
                    "visible_objects": [{"object_id": "7", "name": "cup"}],
                    "action": {"action": "move_to_object", "parameters": {"object_id": "7"}},
                    "expected_valid": True,
                },
                {
                    "visible_objects": [{"object_id": "7", "name": "cup"}],
                    "action": {"action": "move_to_object", "parameters": {"object_id": "7"}},
                    "expected_valid": True,
                },
                {
                    "visible_objects": [{"object_id": "7", "name": "cup"}],
                    "action": {"action": "move_to_object", "parameters": {"object_id": "7"}},
                    "expected_valid": False,
                },
                {
                    "visible_objects": [{"object_id": "7", "name": "cup"}],
                    "action": {"action": "move_and_take_object", "parameters": {"object_id": "99"}},
                    "expected_valid": False,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            result = replay_public_trace(trace, log_dir=temp_dir)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["steps"][2]["failure_class"], "LOOP_ERROR")
        self.assertEqual(result["steps"][3]["failure_class"], "PERCEPTION_ERROR")
        self.assertFalse(result["official_score_verified"])


class FailureAnalyzerTests(unittest.TestCase):
    def test_only_official_verified_failures_are_ranked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics = Path(temp_dir)
            official = {
                "episode_id": "official-1",
                "task_type": "tidyroom",
                "verified": True,
                "termination_reason": "evaluated_by_official_task_service",
            }
            unverified = {
                "episode_id": "local-1",
                "task_type": "npc",
                "verified": False,
                "termination_reason": "local",
            }
            (metrics / "episode_official-1.json").write_text(json.dumps(official), encoding="utf-8")
            (metrics / "episode_local-1.json").write_text(json.dumps(unverified), encoding="utf-8")
            for episode_id, category in (("official-1", "PLACEMENT"), ("local-1", "MODEL_API")):
                report = {
                    "episode_id": episode_id,
                    "task_type": "tidyroom",
                    "first_critical_error": {"category": category, "step": 2, "message": "failed"},
                }
                (metrics / f"failure_{episode_id}.json").write_text(json.dumps(report), encoding="utf-8")
            payload = analyze_failures(metrics)
        self.assertEqual(payload["status"], "VERIFIED_FAILURE_DATA")
        self.assertEqual(payload["official_failures"], 1)
        self.assertEqual(payload["ranked_failures"][0]["category"], "PLACEMENT")

    def test_empty_metrics_are_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = analyze_failures(Path(temp_dir))
        self.assertEqual(payload["status"], "NOT_VERIFIED")
        self.assertEqual(payload["ranked_failures"], [])


if __name__ == "__main__":
    unittest.main()
