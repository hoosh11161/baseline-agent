from __future__ import annotations

import unittest

from arenaagent.competition.evaluation.postconditions import (
    POSTCONDITION_FAILURE,
    POSTCONDITION_SUCCESS,
    POSTCONDITION_UNKNOWN,
    PhysicalPostconditionTracker,
)
from arenaagent.competition.runtime import CompetitionRuntime


class PhysicalPostconditionTests(unittest.TestCase):
    def test_pick_requires_confirmed_hand_state(self) -> None:
        tracker = PhysicalPostconditionTracker()
        objects = {"cup": {"position": [0, 0, 0]}}
        tracker.start(
            {"action": "move_and_take_object", "parameters": {"object_id": "cup"}},
            object_id="cup",
            objects=objects,
            visible_ids={"cup"},
            step=1,
        )
        self.assertEqual(tracker.observe(objects, {"cup"}), [])
        events = tracker.update_hand_state(True, objects, observation_step=1)
        self.assertEqual(events[0].status, POSTCONDITION_SUCCESS)
        self.assertTrue(events[0].evidence["object_in_hand"])

    def test_failed_pick_is_not_treated_as_successful_api_call(self) -> None:
        runtime = CompetitionRuntime()
        runtime.ensure_episode({"task_type": "tidyroom", "subject": "整理", "movable_object_id": ["cup"]})
        runtime.observe([{"object_id": "cup", "position": [0, 0, 0]}])
        runtime.record_action(
            {"action": "move_and_take_object", "parameters": {"object_id": "cup"}},
            {"result": "success"},
        )
        runtime.observe([{"object_id": "cup", "position": [0, 0, 0]}])
        runtime.update_hand_state(False)
        self.assertEqual(runtime.metrics.postcondition_failures, 1)
        self.assertEqual(runtime.first_failure["category"], "PHYSICAL_POSTCONDITION")
        self.assertEqual(runtime.first_failure["step"], 1)

    def test_put_requires_fresh_position_or_remains_unknown(self) -> None:
        tracker = PhysicalPostconditionTracker()
        tracker.start(
            {"action": "put_down_sth", "parameters": {"target_location": [1, 2, 3]}},
            object_id="cup",
            objects={"cup": {}},
            visible_ids={"cup"},
            step=1,
        )
        tracker.observe({"cup": {}}, {"cup"})
        events = tracker.update_hand_state(False, {"cup": {}}, observation_step=1)
        self.assertEqual(events[0].status, POSTCONDITION_UNKNOWN)
        self.assertIn("no fresh public position", events[0].reason)

    def test_put_far_from_target_is_failure(self) -> None:
        tracker = PhysicalPostconditionTracker(placement_tolerance=5)
        tracker.start(
            {"action": "put_down_sth", "parameters": {"target_location": [1, 2, 3]}},
            object_id="cup",
            objects={"cup": {"position": [0, 0, 0]}},
            visible_ids={"cup"},
            step=2,
        )
        current = {"cup": {"position": [100, 100, 100], "position_seen_step": 2}}
        tracker.observe(current, {"cup"})
        events = tracker.update_hand_state(False, current, observation_step=2)
        self.assertEqual(events[0].status, POSTCONDITION_FAILURE)

    def test_slice_uses_real_public_state_change(self) -> None:
        tracker = PhysicalPostconditionTracker()
        before = {"food": {"is_sliced": False}}
        tracker.start(
            {"action": "slice_food", "parameters": {"object_id": "food", "location": [0, 0, 0]}},
            object_id="food",
            objects=before,
            visible_ids={"food"},
            step=1,
        )
        events = tracker.observe({"food": {"is_sliced": True}}, {"food"})
        self.assertEqual(events[0].status, POSTCONDITION_SUCCESS)
        self.assertEqual(events[0].evidence["after"], {"is_sliced": True})

    def test_missing_wash_state_is_unknown_not_success(self) -> None:
        tracker = PhysicalPostconditionTracker()
        objects = {"faucet": {"name": "faucet"}}
        tracker.start(
            {"action": "wash_hands", "parameters": {"faucet_object_id": "faucet"}},
            object_id="faucet",
            objects=objects,
            visible_ids={"faucet"},
            step=1,
        )
        events = tracker.observe(objects, {"faucet"})
        self.assertEqual(events[0].status, POSTCONDITION_UNKNOWN)


if __name__ == "__main__":
    unittest.main()
