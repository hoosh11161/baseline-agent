from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from arenaagent.competition.training_data import export_verified_trajectories


class TrainingDataTests(unittest.TestCase):
    def test_exports_only_official_verified_labeled_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            metrics = root / "metrics"
            metrics.mkdir()
            verified = {
                "episode_id": "official-1",
                "task_type": "counting",
                "success": True,
                "score": 1,
                "verified": True,
                "termination_reason": "evaluated_by_official_task_service",
                "run_metadata": {"model": "test-model"},
                "world_state": {
                    "recent_actions": [
                        {
                            "step": 1,
                            "state": {"visible_object_ids": ["1"]},
                            "action": {"action": "submit_answer", "output": 1},
                            "result": {"answer": "1"},
                            "failed": False,
                        }
                    ]
                },
            }
            unverified = dict(verified, episode_id="fake-1", verified=False)
            (metrics / "episode_official-1.json").write_text(json.dumps(verified), encoding="utf-8")
            (metrics / "episode_fake-1.json").write_text(json.dumps(unverified), encoding="utf-8")

            output = root / "verified.jsonl"
            manifest = export_verified_trajectories(metrics, output)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

            self.assertEqual(manifest["status"], "VERIFIED_DATASET")
            self.assertEqual(manifest["verified_episodes"], 1)
            self.assertEqual(manifest["sample_count"], 1)
            self.assertEqual(rows[0]["episode_id"], "official-1")
            self.assertEqual(rows[0]["label"], "positive")

    def test_failed_episode_does_not_mislabel_successful_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            metrics = root / "metrics"
            metrics.mkdir()
            episode = {
                "episode_id": "official-failed",
                "task_type": "tidyroom",
                "success": False,
                "verified": True,
                "termination_reason": "evaluated_by_official_task_service",
                "world_state": {
                    "recent_actions": [
                        {"step": 1, "action": {"action": "move_forward"}, "result": {}, "failed": False},
                        {"step": 2, "action": {}, "result": {"result": "failed"}, "failed": True},
                    ]
                },
            }
            (metrics / "episode_failed.json").write_text(json.dumps(episode), encoding="utf-8")
            output = root / "verified.jsonl"

            manifest = export_verified_trajectories(metrics, output)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

            self.assertEqual(manifest["label_counts"], {"positive": 0, "negative": 1, "unlabeled": 0})
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["step"], 2)


if __name__ == "__main__":
    unittest.main()
