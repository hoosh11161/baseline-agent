from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

POSTCONDITION_SUCCESS = "SUCCESS"
POSTCONDITION_FAILURE = "FAILURE"
POSTCONDITION_UNKNOWN = "UNKNOWN"
POSTCONDITION_PENDING = "PENDING"
VECTOR_DIMENSIONS = 3

TRACKED_ACTIONS = {
    "move_and_take_object": "pick",
    "put_down_sth": "put",
    "move_and_put_down": "put",
    "move_and_put_down_object_in_container": "put",
    "pour_water": "pour",
    "slice_food": "slice",
    "wash_hands": "wash",
    "wash_object_in_hand": "wash",
    "mop_floor": "mop",
    "sit_down_to_object": "sit",
    "move_to_object": "navigation",
    "move_to_npc": "navigation",
    "move_to_location": "navigation",
    "move_forward": "navigation",
    "move_backward": "navigation",
}

RELEVANT_STATE_FIELDS = {
    "pour": ("filled", "fill_level", "water_level", "contains", "state", "states", "properties"),
    "slice": ("sliced", "is_sliced", "state", "states", "semantic_type", "name", "properties"),
    "wash": ("clean", "is_clean", "cleanliness", "dirty", "state", "states", "properties"),
    "mop": ("clean", "is_clean", "cleanliness", "dirty", "state", "states", "properties"),
    "sit": ("occupied", "is_occupied", "state", "states", "properties"),
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _location(value: Any) -> list[float] | None:
    if isinstance(value, dict):
        lowered = {str(key).lower(): raw for key, raw in value.items()}
        numbers = [_number(lowered.get(axis)) for axis in ("x", "y", "z")]
    elif isinstance(value, (list, tuple)) and len(value) >= VECTOR_DIMENSIONS:
        numbers = [_number(raw) for raw in value[:VECTOR_DIMENSIONS]]
    else:
        return None
    return [float(value) for value in numbers] if all(value is not None for value in numbers) else None


def _position(item: dict[str, Any]) -> list[float] | None:
    direct = _location(item.get("position") or item.get("place_location") or item.get("location"))
    if direct is not None:
        return direct
    bounds = item.get("world_aabb")
    if (
        not isinstance(bounds, dict)
        or not isinstance(bounds.get("min"), dict)
        or not isinstance(bounds.get("max"), dict)
    ):
        return None
    lower = {str(key).lower(): raw for key, raw in bounds["min"].items()}
    upper = {str(key).lower(): raw for key, raw in bounds["max"].items()}
    values: list[float] = []
    for axis in ("x", "y", "z"):
        low = _number(lower.get(axis))
        high = _number(upper.get(axis))
        if low is None or high is None:
            return None
        values.append((low + high) / 2.0)
    return values


def _state_subset(item: dict[str, Any], kind: str) -> dict[str, Any]:
    return {key: item[key] for key in RELEVANT_STATE_FIELDS.get(kind, ()) if key in item}


def _scene_hash(objects: dict[str, dict[str, Any]], visible_ids: set[str]) -> str:
    public = {
        object_id: {
            key: value
            for key, value in item.items()
            if key not in {"first_seen_step", "last_seen_step", "seen_count", "position_seen_step", "counted"}
        }
        for object_id, item in objects.items()
        if object_id in visible_ids
    }
    encoded = json.dumps(public, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


@dataclass(slots=True)
class ActionExpectation:
    action: str
    kind: str
    created_step: int
    object_id: str = ""
    target_location: list[float] | None = None
    status: str = POSTCONDITION_PENDING
    reason: str = "awaiting a post-action observation"
    evidence: dict[str, Any] = field(default_factory=dict)
    observations: int = 0
    before_position: list[float] | None = None
    before_state: dict[str, Any] = field(default_factory=dict)
    before_scene_hash: str = ""

    def context(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "kind": self.kind,
            "created_step": self.created_step,
            "object_id": self.object_id,
            "target_location": self.target_location,
            "status": self.status,
            "reason": self.reason,
            "evidence": self.evidence,
            "observations": self.observations,
        }


class PhysicalPostconditionTracker:
    """Evaluate only postconditions that public observations can support."""

    def __init__(self, *, placement_tolerance: float = 15.0, history_limit: int = 12) -> None:
        self.placement_tolerance = float(placement_tolerance)
        self.history_limit = max(int(history_limit), 1)
        self.pending: ActionExpectation | None = None
        self.history: list[ActionExpectation] = []

    def reset(self) -> None:
        self.pending = None
        self.history = []

    def start(
        self,
        action: dict[str, Any],
        *,
        object_id: str,
        objects: dict[str, dict[str, Any]],
        visible_ids: set[str],
        step: int,
    ) -> list[ActionExpectation]:
        name = str(action.get("action") or "").lower()
        kind = TRACKED_ACTIONS.get(name)
        if kind is None:
            return []
        completed: list[ActionExpectation] = []
        if self.pending is not None:
            completed.append(self._finish(POSTCONDITION_UNKNOWN, "superseded before verification"))
        params = action.get("parameters") or {}
        target = None
        for key in ("put_target_location", "put_location", "target_location", "move_target_location", "location"):
            target = _location(params.get(key))
            if target is not None:
                break
        before = objects.get(object_id, {})
        self.pending = ActionExpectation(
            action=name,
            kind=kind,
            created_step=int(step),
            object_id=str(object_id or ""),
            target_location=target,
            before_position=_position(before),
            before_state=_state_subset(before, kind),
            before_scene_hash=_scene_hash(objects, visible_ids),
        )
        return completed

    def observe(  # noqa: PLR0911
        self,
        objects: dict[str, dict[str, Any]],
        visible_ids: set[str],
        *,
        official_completion: bool = False,
    ) -> list[ActionExpectation]:
        expectation = self.pending
        if expectation is None:
            return []
        expectation.observations += 1
        if expectation.kind in {"pick", "put"}:
            return []
        if official_completion:
            return [self._finish(POSTCONDITION_SUCCESS, "official task response reports completion")]
        after = objects.get(expectation.object_id, {})
        if expectation.kind in RELEVANT_STATE_FIELDS:
            after_state = _state_subset(after, expectation.kind)
            if expectation.before_state and after_state and after_state != expectation.before_state:
                return [
                    self._finish(
                        POSTCONDITION_SUCCESS,
                        "public task-relevant state changed",
                        {"before": expectation.before_state, "after": after_state},
                    )
                ]
            return [
                self._finish(
                    POSTCONDITION_UNKNOWN,
                    "no public task-relevant state field proved the physical effect",
                    {"available_fields": sorted(after_state)},
                )
            ]
        if expectation.kind == "navigation":
            after_hash = _scene_hash(objects, visible_ids)
            if after_hash != expectation.before_scene_hash:
                return [
                    self._finish(
                        POSTCONDITION_SUCCESS,
                        "public scene changed after navigation",
                        {"scene_changed": True},
                    )
                ]
            return [
                self._finish(
                    POSTCONDITION_UNKNOWN,
                    "navigation result returned no observable public scene change",
                    {"scene_changed": False},
                )
            ]
        return []

    def update_hand_state(
        self,
        has_object: bool,
        objects: dict[str, dict[str, Any]],
        *,
        observation_step: int | None,
    ) -> list[ActionExpectation]:
        expectation = self.pending
        if expectation is None or expectation.kind not in {"pick", "put"} or expectation.observations < 1:
            return []
        if expectation.kind == "pick":
            status = POSTCONDITION_SUCCESS if has_object else POSTCONDITION_FAILURE
            reason = "hand state confirms pickup" if has_object else "hand remained empty after pickup"
            return [self._finish(status, reason, {"object_in_hand": bool(has_object)})]
        if has_object:
            return [
                self._finish(
                    POSTCONDITION_FAILURE,
                    "object remained in hand after placement",
                    {"object_in_hand": True},
                )
            ]
        after = objects.get(expectation.object_id, {})
        is_fresh = observation_step is not None and after.get("position_seen_step") == observation_step
        after_position = _position(after) if is_fresh else None
        if expectation.target_location is not None and after_position is not None:
            distance = math.dist(after_position, expectation.target_location)
            status = POSTCONDITION_SUCCESS if distance <= self.placement_tolerance else POSTCONDITION_FAILURE
            reason = (
                "fresh position confirms placement"
                if status == POSTCONDITION_SUCCESS
                else "object is far from target"
            )
            return [
                self._finish(
                    status,
                    reason,
                    {"object_in_hand": False, "position": after_position, "distance_to_target": round(distance, 3)},
                )
            ]
        return [
            self._finish(
                POSTCONDITION_UNKNOWN,
                "hand is empty but no fresh public position proves placement",
                {"object_in_hand": False, "fresh_position": False},
            )
        ]

    def _finish(self, status: str, reason: str, evidence: dict[str, Any] | None = None) -> ActionExpectation:
        if self.pending is None:
            raise RuntimeError("no pending postcondition")
        self.pending.status = status
        self.pending.reason = reason
        self.pending.evidence = dict(evidence or {})
        completed = self.pending
        self.pending = None
        self.history.append(completed)
        self.history = self.history[-self.history_limit :]
        return completed

    def context(self) -> dict[str, Any]:
        return {
            "pending": self.pending.context() if self.pending else None,
            "recent": [item.context() for item in self.history[-5:]],
        }
