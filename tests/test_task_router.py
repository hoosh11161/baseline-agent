from __future__ import annotations

import unittest

from arenaagent.competition.runtime import CompetitionRuntime
from arenaagent.competition.task_router import TaskStrategyRouter


class TaskStrategyRouterTests(unittest.TestCase):
    def test_high_confidence_held_jigsaw_piece_is_placed_without_vlm(self) -> None:
        subject = {
            "task_id": "jigsaw-router-1",
            "task_type": "jigsaw",
            "subject": "完成拼图",
            "reference_bounding": [0, 100, 100, 0],
            "rows": 2,
            "columns": 2,
            "piece_object_id": ["piece-a"],
        }
        runtime = CompetitionRuntime()
        runtime.ensure_episode(subject)
        runtime.observe(
            [
                {"object_id": "reference", "position": [10, 25, 25]},
                {"object_id": "piece-a", "position": [99, 25, 25]},
            ]
        )
        runtime.record_action(
            {"action": "move_and_take_object", "parameters": {"object_id": "piece-a"}},
            {"result": "success"},
        )
        runtime.update_hand_state(True)
        router = TaskStrategyRouter()
        router.observe(runtime, subject)

        action = router.propose_action(subject, runtime)

        self.assertIsNotNone(action)
        self.assertEqual(action["action"], "put_down_sth")
        self.assertEqual(action["parameters"]["target_location"], [10.0, 75.0, 25.0])
        self.assertEqual(
            action["parameters"]["target_rotation"],
            {"roll": 0.0, "yaw": 0.0, "pitch": 0.0},
        )
        self.assertTrue(runtime.validate_action(action, object_in_hand=True).valid)

    def test_incomplete_jigsaw_evidence_falls_back_to_vlm(self) -> None:
        subject = {
            "task_id": "jigsaw-router-2",
            "task_type": "jigsaw",
            "subject": "完成拼图",
            "reference_bounding": [0, 100, 100, 0],
            "rows": 2,
            "columns": 2,
            "piece_object_id": ["piece-a"],
        }
        runtime = CompetitionRuntime()
        runtime.ensure_episode(subject)
        runtime.observe([{"object_id": "piece-a", "position": [99, 25, 25]}])
        runtime.record_action(
            {"action": "move_and_take_object", "parameters": {"object_id": "piece-a"}},
            {"result": "success"},
        )
        runtime.update_hand_state(True)
        router = TaskStrategyRouter()
        router.observe(runtime, subject)

        self.assertIsNone(router.propose_action(subject, runtime))


if __name__ == "__main__":
    unittest.main()
