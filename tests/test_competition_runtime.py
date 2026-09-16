from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from arenaagent.competition.runtime import CompetitionRuntime, classify_failure, route_task


class CompetitionRuntimeTests(unittest.TestCase):
    def make_runtime(self) -> CompetitionRuntime:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        return CompetitionRuntime(log_dir=self.temp_dir.name, repeated_action_limit=2, stagnant_observation_limit=3)

    def test_routes_all_official_task_types(self) -> None:
        self.assertEqual(route_task({"task_type": "counting"}), "counting")
        self.assertEqual(route_task({"stage": "raven_room"}), "raven")
        self.assertEqual(route_task({"subject": "请完成拼图"}), "jigsaw")
        self.assertEqual(route_task({"subject": "去询问赵爷爷"}), "npc")
        self.assertEqual(route_task({"subject": "请整理房间"}), "tidyroom")

    def test_blocks_hallucinated_object_id_before_environment_call(self) -> None:
        runtime = self.make_runtime()
        runtime.ensure_episode({"task_type": "tidyroom", "subject": "整理"})
        runtime.observe([{"object_id": "7", "name": "cup"}])
        decision = runtime.validate_action(
            {"action": "move_and_take_object", "parameters": {"object_id": "999"}, "output": 0}
        )
        self.assertFalse(decision.valid)
        self.assertEqual(decision.failure_class, "PERCEPTION_ERROR")
        self.assertEqual(runtime.metrics.invalid_actions, 1)

    def test_blocks_repeated_action_loop(self) -> None:
        runtime = self.make_runtime()
        runtime.ensure_episode({"task_type": "tidyroom", "subject": "整理"})
        runtime.observe([{"object_id": "7", "name": "cup"}])
        action = {"action": "move_to_object", "parameters": {"object_id": "7"}, "output": 0}
        for _ in range(2):
            decision = runtime.validate_action(action)
            self.assertTrue(decision.valid)
            runtime.record_action(action, {"result": "success"}, validation=decision)
        third = runtime.validate_action(action)
        self.assertFalse(third.valid)
        self.assertEqual(third.failure_class, "LOOP_ERROR")

    def test_raven_ranked_retries_are_not_mistaken_for_a_loop(self) -> None:
        runtime = self.make_runtime()
        runtime.ensure_episode({"task_type": "raven", "subject": "瑞文"})
        action = {"action": "solve_raven", "parameters": {}, "output": 0}
        for _ in range(3):
            decision = runtime.validate_action(action)
            self.assertTrue(decision.valid)
            runtime.record_action(action, {"answer": [1, 2, 3]}, validation=decision)
        fourth = runtime.validate_action(action)
        self.assertFalse(fourth.valid)
        self.assertEqual(fourth.failure_class, "REASONING_ERROR")

    def test_count_registry_deduplicates_stable_ids(self) -> None:
        runtime = self.make_runtime()
        runtime.ensure_episode({"task_type": "counting", "subject": "多少红色物体"})
        runtime.observe([{"object_id": "1", "color": "Red"}, {"object_id": "2", "color": "Blue"}])
        runtime.observe([{"object_id": "1", "color": "Red"}, {"object_id": "3", "color": "Red"}])
        state = runtime.prompt_context()
        self.assertEqual(state["object_registry"]["unique_objects_seen"], 3)
        self.assertEqual(state["object_registry"]["counts"]["color"], {"Blue": 1, "Red": 2})
        self.assertEqual(state["observation_diff"]["appeared"], ["3"])
        self.assertEqual(state["observation_diff"]["disappeared"], ["2"])

    def test_count_registry_matches_remapped_id_by_public_position(self) -> None:
        runtime = self.make_runtime()
        runtime.ensure_episode({"task_type": "counting", "subject": "多少红色物体"})
        runtime.observe(
            [
                {
                    "object_id": "1",
                    "name": "cup",
                    "color": "Red",
                    "world_aabb": {"min": {"X": 0, "Y": 0, "Z": 0}, "max": {"X": 2, "Y": 2, "Z": 2}},
                }
            ]
        )
        runtime.observe(
            [
                {
                    "object_id": "9",
                    "name": "cup",
                    "color": "Red",
                    "world_aabb": {"min": {"X": 1, "Y": 0, "Z": 0}, "max": {"X": 3, "Y": 2, "Z": 2}},
                }
            ]
        )
        self.assertEqual(len(runtime.objects), 1)
        self.assertEqual(runtime.objects["1"]["source_ids"], ["1", "9"])
        self.assertEqual(runtime.visible_object_ids, {"9"})

    def test_secondary_dedup_does_not_merge_distant_objects(self) -> None:
        runtime = self.make_runtime()
        runtime.ensure_episode({"task_type": "counting", "subject": "多少红色物体"})
        runtime.observe(
            [
                {
                    "object_id": "1",
                    "name": "cup",
                    "color": "Red",
                    "place_location": {"X": 0, "Y": 0, "Z": 0},
                }
            ]
        )
        runtime.observe(
            [
                {
                    "object_id": "9",
                    "name": "cup",
                    "color": "Red",
                    "place_location": {"X": 100, "Y": 0, "Z": 0},
                }
            ]
        )
        self.assertEqual(len(runtime.objects), 2)

    def test_empty_hand_put_is_blocked(self) -> None:
        runtime = self.make_runtime()
        runtime.ensure_episode({"task_type": "jigsaw", "subject": "拼图"})
        decision = runtime.validate_action(
            {"action": "put_down_sth", "parameters": {"target_location": [1, 2, 3]}, "output": 0},
            object_in_hand=False,
        )
        self.assertFalse(decision.valid)

    def test_failure_artifacts_are_written(self) -> None:
        runtime = self.make_runtime()
        runtime.ensure_episode({"task_id": "episode-1", "task_type": "counting", "subject": "计数"})
        runtime.observe([])
        decision = runtime.validate_action({})
        runtime.record_action({}, {"result": "failed"}, validation=decision)
        payload = runtime.finish({"success": False, "score": 0})
        self.assertFalse(payload["success"])
        metrics_dir = Path(self.temp_dir.name) / "metrics"
        self.assertTrue((metrics_dir / "episode_episode-1.json").exists())
        report = json.loads((metrics_dir / "failure_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report[0]["first_critical_error"]["error_type"], "ACTION_ERROR")
        self.assertEqual(report[0]["first_critical_error"]["category"], "JSON_PARSE")

    def test_failure_taxonomy_maps_task_specific_errors(self) -> None:
        self.assertEqual(classify_failure("MODEL_ERROR", "timeout", {}, "tidyroom"), "MODEL_API")
        self.assertEqual(classify_failure("REASONING_ERROR", "wrong", {}, "raven"), "RAVEN_REASONING")
        self.assertEqual(
            classify_failure("ACTION_ERROR", "failed", {"action": "put_down_sth"}, "tidyroom"),
            "PLACEMENT",
        )


if __name__ == "__main__":
    unittest.main()
