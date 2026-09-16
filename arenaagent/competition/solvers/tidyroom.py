from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


def _as_ids(value: Any) -> set[str]:
    if value in (None, "", []):
        return set()
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return {str(item) for item in values if item not in (None, "")}


def _failed(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    status = str(result.get("result") or result.get("status") or "").strip().lower()
    return status in {"failed", "failure", "error", "false"} or result.get("success") is False


@dataclass(slots=True)
class TidyRoomTracker:
    retry_limit: int = 2
    expected_objects: set[str] = field(default_factory=set)
    completed_objects: set[str] = field(default_factory=set)
    failed_objects: set[str] = field(default_factory=set)
    states: dict[str, str] = field(default_factory=dict)
    retries: Counter[str] = field(default_factory=Counter)
    current_object: str | None = None
    pending_pick: str | None = None
    pending_place: str | None = None
    completed_goal_actions: int = 0
    completion_evidence: bool = False

    def reset(self, subject: dict[str, Any]) -> None:
        self.expected_objects = _as_ids(subject.get("movable_object_id")) | _as_ids(subject.get("piece_object_id"))
        self.completed_objects = set()
        self.failed_objects = set()
        self.states = {object_id: "DISCOVERED" for object_id in self.expected_objects}
        self.retries = Counter()
        self.current_object = None
        self.pending_pick = None
        self.pending_place = None
        self.completed_goal_actions = 0
        self.completion_evidence = False

    def observe(self, known_objects: dict[str, dict[str, Any]], completion_evidence: bool = False) -> None:
        self.completion_evidence = self.completion_evidence or bool(completion_evidence)
        for object_id in known_objects:
            if object_id in self.expected_objects:
                if self.states.get(object_id, "DISCOVERED") == "DISCOVERED":
                    self.states[object_id] = "TARGET_IDENTIFIED"

    def update_hand_state(self, has_object: bool) -> None:
        if self.pending_pick is not None:
            object_id = self.pending_pick
            self.pending_pick = None
            if has_object:
                self.current_object = object_id
                self.states[object_id] = "PICKED"
            else:
                self._record_failure(object_id)
        if self.pending_place is not None:
            object_id = self.pending_place
            self.pending_place = None
            if not has_object:
                self.completed_objects.add(object_id)
                self.expected_objects.discard(object_id)
                self.states[object_id] = "VERIFIED"
                self.current_object = None
            else:
                self.states[object_id] = "PICKED"
                self._record_failure(object_id)

    def record_action(self, action: dict[str, Any], result: Any, canonical_object_id: str = "") -> None:
        name = str(action.get("action") or "").lower()
        object_id = canonical_object_id or self.current_object or ""
        if _failed(result):
            if object_id:
                self._record_failure(object_id)
            return
        if name in {"move_to_object", "look_at_object"} and object_id:
            self.states[object_id] = "APPROACHING"
        elif name == "move_and_take_object" and object_id:
            self.current_object = object_id
            self.pending_pick = object_id
            self.states[object_id] = "APPROACHING"
        elif name in {"move_to_location", "move_forward", "move_backward"} and self.current_object:
            self.states[self.current_object] = "MOVING"
        elif name in {"put_down_sth", "move_and_put_down", "move_and_put_down_object_in_container"}:
            if self.current_object:
                self.pending_place = self.current_object
                self.states[self.current_object] = "PLACED"
        elif name in {
            "pour_water",
            "slice_food",
            "wash_hands",
            "wash_object_in_hand",
            "mop_floor",
            "sit_down_to_object",
            "rest",
        }:
            self.completed_goal_actions += 1

    def _record_failure(self, object_id: str) -> None:
        self.retries[object_id] += 1
        self.states[object_id] = "DISCOVERED"
        if self.retries[object_id] > self.retry_limit:
            self.failed_objects.add(object_id)

    def can_finish(self, task_type: str, object_in_hand: bool) -> tuple[bool, str]:
        if task_type not in {"tidyroom", "jigsaw"}:
            return True, "not a behavior task"
        if object_in_hand or self.current_object or self.pending_pick or self.pending_place:
            return False, "an object is held or awaiting pick/place verification"
        if self.expected_objects:
            return False, f"unfinished objects remain: {sorted(self.expected_objects)}"
        if self.completion_evidence:
            return True, "official task response reports completion"
        if self.completed_objects or self.completed_goal_actions:
            return True, "at least one goal action was verified and no known subgoal remains"
        return False, "no verified completion evidence"

    def context(self) -> dict[str, Any]:
        return {
            "states": dict(sorted(self.states.items())),
            "completed_objects": sorted(self.completed_objects),
            "failed_objects": sorted(self.failed_objects),
            "current_object": self.current_object,
            "pending_pick": self.pending_pick,
            "pending_place": self.pending_place,
            "retry_count": dict(sorted(self.retries.items())),
            "remaining_objects": sorted(self.expected_objects),
            "completion_evidence": self.completion_evidence,
        }
