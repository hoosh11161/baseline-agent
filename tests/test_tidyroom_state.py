from __future__ import annotations

import unittest

from arenaagent.competition.runtime import CompetitionRuntime


class TidyRoomStateTests(unittest.TestCase):
    def make_runtime(self) -> CompetitionRuntime:
        runtime = CompetitionRuntime(repeated_action_limit=2)
        runtime.ensure_episode(
            {"task_type": "tidyroom", "subject": "整理房间", "movable_object_id": ["7"]}
        )
        runtime.observe([{"object_id": "7", "name": "cup"}])
        return runtime

    def test_pick_and_place_require_hand_state_verification(self) -> None:
        runtime = self.make_runtime()
        take = {"action": "move_and_take_object", "parameters": {"object_id": "7"}, "output": 0}
        runtime.record_action(take, {"result": "success"})
        self.assertEqual(runtime.progress.context()["pending_pick"], "7")
        runtime.update_hand_state(True)
        self.assertEqual(runtime.progress.context()["states"]["7"], "PICKED")

        put = {"action": "put_down_sth", "parameters": {"target_location": [1, 2, 3]}, "output": 0}
        runtime.record_action(put, {"result": "success"})
        self.assertEqual(runtime.progress.context()["states"]["7"], "PLACED")
        runtime.update_hand_state(False)
        self.assertEqual(runtime.progress.context()["states"]["7"], "VERIFIED")
        self.assertEqual(runtime.progress.context()["remaining_objects"], [])

    def test_finish_guard_blocks_premature_finish(self) -> None:
        runtime = self.make_runtime()
        decision = runtime.validate_action(
            {"action": "finish_task", "parameters": {}, "output": 0}, object_in_hand=False
        )
        self.assertFalse(decision.valid)
        self.assertEqual(decision.failure_class, "PREMATURE_FINISH")

    def test_finish_guard_allows_verified_completion(self) -> None:
        runtime = self.make_runtime()
        runtime.progress.completed_objects.add("7")
        runtime.progress.expected_objects.clear()
        runtime.progress.states["7"] = "VERIFIED"
        decision = runtime.validate_action(
            {"action": "finish_task", "parameters": {}, "output": 0}, object_in_hand=False
        )
        self.assertTrue(decision.valid)

    def test_completed_object_cannot_be_picked_again(self) -> None:
        runtime = self.make_runtime()
        runtime.progress.completed_objects.add("7")
        runtime.progress.expected_objects.clear()
        decision = runtime.validate_action(
            {"action": "move_and_take_object", "parameters": {"object_id": "7"}, "output": 0}
        )
        self.assertFalse(decision.valid)
        self.assertEqual(decision.failure_class, "PLANNING_ERROR")


if __name__ == "__main__":
    unittest.main()
