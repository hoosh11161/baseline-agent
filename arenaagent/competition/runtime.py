from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASK_TYPES = {"tidyroom", "counting", "npc", "raven", "jigsaw", "unknown"}
VECTOR_DIMENSIONS = 3
EARLY_PHASE_RATIO = 0.65
MID_PHASE_RATIO = 0.3
CRITICAL_REMAINING_STEPS = 5
MAX_RAVEN_ATTEMPTS = 3
OBJECT_ACTIONS = {
    "look_at_object",
    "point_at_object",
    "move_and_take_object",
    "move_to_object",
    "pour_water",
    "sit_down_to_object",
    "slice_food",
    "wash_hands",
    "wash_object_in_hand",
    "mop_floor",
}
TERMINAL_ACTIONS = {"finish_task", "submit_answer", "submit_puzzle_answer", "solve_raven"}
SUPPORTED_ACTIONS = {
    "finish_task",
    "submit_answer",
    "submit_puzzle_answer",
    "solve_raven",
    "look_at_location",
    "look_at_object",
    "point_at_object",
    "move_and_take_object",
    "move_forward",
    "move_backward",
    "put_down_sth",
    "turn_in_degree",
    "turn_around_to_degree",
    "move_to_object",
    "move_to_npc",
    "move_to_location",
    "pour_water",
    "sit_down_to_object",
    "slice_food",
    "wash_hands",
    "wash_object_in_hand",
    "mop_floor",
    "rest",
    "speak_to_npc",
    "move_and_put_down",
    "move_and_put_down_object_in_container",
}


def route_task(subject: Any) -> str:
    """Return one of the five official preliminary task types or ``unknown``."""
    if isinstance(subject, dict):
        direct = str(subject.get("task_type") or "").strip().lower()
        if direct in TASK_TYPES:
            return direct
        stage = str(subject.get("stage") or "").strip().lower()
        stage_aliases = {
            "raven_room": "raven",
            "npc_room": "npc",
            "counting_room": "counting",
            "tidy_room": "tidyroom",
            "jigsaw_room": "jigsaw",
        }
        if stage in stage_aliases:
            return stage_aliases[stage]
        text = " ".join(str(subject.get(k) or "") for k in ("subject", "goal", "task_prompt"))
    else:
        text = str(subject or "")
    lowered = text.lower()
    keyword_routes = (
        ("raven", ("raven", "瑞文")),
        ("jigsaw", ("jigsaw", "拼图")),
        ("npc", ("npc", "对话", "询问", "问问")),
        ("counting", ("count", "多少", "几种", "数量")),
        ("tidyroom", ("tidy", "整理", "收拾", "摆放")),
    )
    for task_type, keywords in keyword_routes:
        if any(keyword in lowered for keyword in keywords):
            return task_type
    return "unknown"


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, float):
        return round(value, 3)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def _hash(value: Any) -> str:
    encoded = json.dumps(_canonical(value), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _object_id(item: dict[str, Any]) -> str:
    for key in ("object_id", "id", "objectId"):
        value = item.get(key)
        if value is not None and not isinstance(value, bool):
            return str(value)
    return ""


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _is_location(value: Any) -> bool:
    if isinstance(value, (list, tuple)):
        return len(value) >= VECTOR_DIMENSIONS and all(
            _as_number(item) is not None for item in value[:VECTOR_DIMENSIONS]
        )
    if isinstance(value, dict):
        lowered = {str(key).lower(): item for key, item in value.items()}
        return all(axis in lowered and _as_number(lowered[axis]) is not None for axis in ("x", "y", "z"))
    return False


def _result_failed(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    status = str(result.get("result") or result.get("status") or "").strip().lower()
    return status in {"failed", "failure", "error", "false"} or result.get("success") is False


def _result_success(result: Any) -> bool:
    if not isinstance(result, dict):
        return result is not None
    status = str(result.get("result") or result.get("status") or "").strip().lower()
    return status in {"success", "succeeded", "ok", "completed", "true"} or result.get("success") is True


def _extract_numeric(value: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                number = _as_number(value[key])
                if number is not None:
                    return number
        for child in value.values():
            found = _extract_numeric(child, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _extract_numeric(child, keys)
            if found is not None:
                return found
    return None


@dataclass(slots=True)
class ActionValidation:
    valid: bool
    action: dict[str, Any]
    error: str = ""
    failure_class: str = ""


@dataclass(slots=True)
class EpisodeMetrics:
    episode_id: str
    task_type: str
    task_text: str
    success: bool | None = None
    score: float | None = None
    steps: int = 0
    invalid_actions: int = 0
    replans: int = 0
    retries: int = 0
    llm_calls: int = 0
    vision_calls: int = 0
    tokens: int = 0
    latency: float = 0.0
    stuck_count: int = 0
    termination_reason: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""
    verified: bool = False


class CompetitionRuntime:
    """Compact world state, action guard, metrics, and failure classification.

    The runtime uses only the public subject, perception and action results.  It
    never queries evaluator internals or hidden task state.
    """

    def __init__(
        self,
        *,
        log_dir: str = "logs",
        repeated_action_limit: int = 2,
        stagnant_observation_limit: int = 5,
        default_max_steps: int = 60,
    ) -> None:
        self.log_dir = Path(log_dir)
        self.repeated_action_limit = max(int(repeated_action_limit), 1)
        self.stagnant_observation_limit = max(int(stagnant_observation_limit), 2)
        self.default_max_steps = max(int(default_max_steps), 1)
        self.metrics: EpisodeMetrics | None = None
        self.subject: dict[str, Any] = {}
        self.max_steps = self.default_max_steps
        self.objects: dict[str, dict[str, Any]] = {}
        self.visible_object_ids: set[str] = set()
        self.observation_hashes: list[str] = []
        self.action_records: list[dict[str, Any]] = []
        self.failed_signatures: Counter[str] = Counter()
        self.questions_asked: set[tuple[str, str]] = set()
        self.npc_facts: list[dict[str, Any]] = []
        self.first_failure: dict[str, Any] | None = None
        self.last_observation_diff: dict[str, list[str]] = {
            "appeared": [],
            "disappeared": [],
            "changed": [],
        }
        self._started_monotonic = 0.0
        self._last_subject_key = ""

    @property
    def task_type(self) -> str:
        return self.metrics.task_type if self.metrics else "unknown"

    def ensure_episode(self, subject: Any) -> None:
        subject_dict = dict(subject) if isinstance(subject, dict) else {"subject": str(subject or "")}
        identity_payload = {
            key: subject_dict.get(key)
            for key in ("task_id", "subject_id", "id", "task_type", "stage", "subject", "goal")
            if subject_dict.get(key) is not None
        }
        subject_key = _hash(identity_payload)
        if self.metrics is not None and subject_key == self._last_subject_key:
            return
        if self.metrics is not None:
            self.finish(termination_reason="subject_changed_without_evaluation")
        self.subject = subject_dict
        task_text = str(
            subject_dict.get("subject") or subject_dict.get("goal") or subject_dict.get("task_prompt") or ""
        )
        episode_hint = subject_dict.get("task_id") or subject_dict.get("subject_id") or subject_dict.get("id")
        episode_id = str(episode_hint or f"{int(time.time() * 1000)}-{subject_key[:8]}")
        self.metrics = EpisodeMetrics(episode_id=episode_id, task_type=route_task(subject_dict), task_text=task_text)
        self.max_steps = self._resolve_max_steps(subject_dict)
        self.objects = {}
        self.visible_object_ids = set()
        self.observation_hashes = []
        self.action_records = []
        self.failed_signatures = Counter()
        self.questions_asked = set()
        self.npc_facts = []
        self.first_failure = None
        self.last_observation_diff = {"appeared": [], "disappeared": [], "changed": []}
        self._started_monotonic = time.perf_counter()
        self._last_subject_key = subject_key

    def _resolve_max_steps(self, source: Any) -> int:
        value = _extract_numeric(source, ("max_steps", "step_limit", "max_step", "steps_limit"))
        return max(int(value), 1) if value is not None else self.default_max_steps

    def observe(self, visible_objects: Any, task_response: Any = None) -> None:
        if self.metrics is None:
            return
        objects = visible_objects if isinstance(visible_objects, list) else []
        previous_visible_ids = set(self.visible_object_ids)
        previous_objects = {
            object_id: {
                key: value
                for key, value in item.items()
                if key not in {"first_seen_step", "last_seen_step", "seen_count"}
            }
            for object_id, item in self.objects.items()
        }
        self.visible_object_ids = set()
        current_objects: dict[str, dict[str, Any]] = {}
        for raw in objects:
            if not isinstance(raw, dict):
                continue
            object_id = _object_id(raw)
            if not object_id:
                continue
            self.visible_object_ids.add(object_id)
            current_objects[object_id] = _canonical(raw)
            existing = dict(self.objects.get(object_id, {}))
            existing.update(_canonical(raw))
            existing.setdefault("first_seen_step", self.metrics.steps)
            existing["last_seen_step"] = self.metrics.steps
            existing["seen_count"] = int(existing.get("seen_count", 0)) + 1
            self.objects[object_id] = existing
        self.last_observation_diff = {
            "appeared": sorted(self.visible_object_ids - previous_visible_ids),
            "disappeared": sorted(previous_visible_ids - self.visible_object_ids),
            "changed": sorted(
                object_id
                for object_id in self.visible_object_ids & previous_visible_ids
                if current_objects.get(object_id) != previous_objects.get(object_id)
            ),
        }
        observation_hash = _hash(objects)
        self.observation_hashes.append(observation_hash)
        self.observation_hashes = self.observation_hashes[-self.stagnant_observation_limit :]
        if (
            len(self.observation_hashes) == self.stagnant_observation_limit
            and len(set(self.observation_hashes)) == 1
            and self.action_records
        ):
            self.metrics.stuck_count += 1
        self._capture_npc_facts(task_response)

    def _capture_npc_facts(self, task_response: Any) -> None:
        if not isinstance(task_response, dict):
            return
        for key in ("npc_reply", "reply", "hints", "facts"):
            value = task_response.get(key)
            if value not in (None, "", {}, []):
                fact = {"step": self.metrics.steps if self.metrics else 0, "source": key, "value": _canonical(value)}
                if fact not in self.npc_facts:
                    self.npc_facts.append(fact)

    def record_npc_exchange(self, target: str, question: str, reply: Any, hints: Any = None) -> None:
        if self.metrics is None:
            return
        self.questions_asked.add((str(target), str(question)))
        fact = {
            "step": self.metrics.steps + 1,
            "source": str(target),
            "question": str(question),
            "reply": _canonical(reply),
            "hints": _canonical(hints),
        }
        if fact not in self.npc_facts:
            self.npc_facts.append(fact)

    def record_llm_call(self, token_usage: Any = None) -> None:
        if self.metrics is None:
            return
        self.metrics.llm_calls += 1
        if isinstance(token_usage, dict):
            total = token_usage.get("total_tokens")
            if _as_number(total) is not None:
                self.metrics.tokens += int(float(total))

    def record_vision_call(self) -> None:
        if self.metrics is not None:
            self.metrics.vision_calls += 1

    def validate_action(  # noqa: PLR0911, PLR0912
        self, action: Any, *, object_in_hand: bool = False
    ) -> ActionValidation:
        if self.metrics is None:
            raise RuntimeError("ensure_episode must be called before validate_action")
        if not isinstance(action, dict) or not action:
            return self._invalid({}, "empty or malformed model action", "ACTION_ERROR")
        normalized = dict(action)
        name = str(normalized.get("action") or "").strip().lower()
        if not name:
            return self._invalid(normalized, "missing action name", "ACTION_ERROR")
        if name not in SUPPORTED_ACTIONS:
            return self._invalid(normalized, f"unsupported action type: {name}", "ACTION_ERROR")
        params = normalized.get("parameters")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return self._invalid(normalized, "parameters must be an object", "ACTION_ERROR")
        normalized["action"] = name
        normalized["parameters"] = params

        required: dict[str, tuple[str, ...]] = {
            "look_at_location": ("target_location", "location"),
            "look_at_object": ("object_id", "object"),
            "point_at_object": ("object_id", "object"),
            "move_and_take_object": ("object_id", "object"),
            "put_down_sth": ("target_location",),
            "move_to_object": ("object_id", "object"),
            "move_to_npc": ("npc_name", "npc", "target", "name"),
            "move_to_location": ("target_location", "location"),
            "speak_to_npc": ("npc_name", "npc", "npc_id", "target", "name"),
            "sit_down_to_object": ("object_id", "object"),
            "wash_hands": ("faucet_object_id", "object_id", "object"),
            "wash_object_in_hand": ("faucet_object_id", "object_id", "object"),
            "mop_floor": ("dirt_id", "object_id", "object"),
        }
        aliases = required.get(name)
        if aliases and not any(params.get(key) not in (None, "") for key in aliases):
            return self._invalid(normalized, f"missing required parameter: {' or '.join(aliases)}", "ACTION_ERROR")

        if name == "move_and_put_down":
            if not any(params.get(key) is not None for key in ("move_target_location", "move_location")):
                return self._invalid(normalized, "missing move_target_location", "ACTION_ERROR")
            if not any(
                params.get(key) is not None for key in ("put_target_location", "put_location", "target_location")
            ):
                return self._invalid(normalized, "missing put_target_location", "ACTION_ERROR")

        if name in OBJECT_ACTIONS:
            object_keys = ("object_id", "object", "faucet_object_id", "dirt_id")
            object_id = next((str(params[key]) for key in object_keys if params.get(key) not in (None, "")), "")
            if object_id and object_id not in self.visible_object_ids:
                return self._invalid(
                    normalized,
                    f"object_id {object_id!r} is not in the current visible-object mapping",
                    "PERCEPTION_ERROR",
                )

        location_keys = (
            "target_location",
            "location",
            "move_target_location",
            "move_location",
            "put_target_location",
            "put_location",
        )
        for key in location_keys:
            if key in params and params[key] is not None and not _is_location(params[key]):
                return self._invalid(normalized, f"{key} must be a finite 3D location", "ACTION_ERROR")

        if name in {"move_forward", "move_backward"}:
            distance = _as_number(params.get("distance", params.get("step")))
            if distance is None or distance <= 0:
                return self._invalid(normalized, "distance must be a positive finite number", "ACTION_ERROR")
        if name in {"turn_in_degree", "turn_around_to_degree"}:
            if _as_number(params.get("degree")) is None:
                return self._invalid(normalized, "degree must be a finite number", "ACTION_ERROR")
        if (
            name in {"put_down_sth", "move_and_put_down", "move_and_put_down_object_in_container"}
            and not object_in_hand
        ):
            return self._invalid(normalized, "cannot place an object while both hands are empty", "ACTION_ERROR")
        if name in {"submit_answer", "submit_puzzle_answer"} and normalized.get("output") in (None, ""):
            return self._invalid(normalized, "submit_answer requires a non-empty output", "TERMINATION_ERROR")
        if name == "finish_task" and self.task_type in {"counting", "npc", "raven"}:
            return self._invalid(
                normalized, f"{self.task_type} requires an answer submission, not finish_task", "TERMINATION_ERROR"
            )

        signature = self.action_signature(normalized)
        # solve_raven advances through a cached ranked candidate list internally,
        # so a few identical public actions are distinct attempts, but retries
        # are still bounded to avoid an endless candidate loop.
        if name == "solve_raven":
            raven_attempts = sum(record["action"].get("action") == "solve_raven" for record in self.action_records)
            if raven_attempts >= MAX_RAVEN_ATTEMPTS:
                return self._invalid(normalized, "maximum Raven candidate attempts reached", "REASONING_ERROR")
        else:
            recent = [record["signature"] for record in self.action_records[-self.repeated_action_limit :]]
            if len(recent) == self.repeated_action_limit and all(item == signature for item in recent):
                return self._invalid(
                    normalized, "repeated-action loop blocked; choose a different observation or plan", "LOOP_ERROR"
                )
            if self.failed_signatures[signature] >= self.repeated_action_limit:
                return self._invalid(
                    normalized, "action is temporarily blacklisted after repeated failures", "LOOP_ERROR"
                )
        if name == "speak_to_npc":
            target = str(next((params[key] for key in ("npc_name", "npc", "target", "name") if params.get(key)), ""))
            message = str(next((params[key] for key in ("message", "content", "text") if params.get(key)), ""))
            if (target, message) in self.questions_asked:
                return self._invalid(normalized, "duplicate NPC question blocked", "MEMORY_ERROR")
        return ActionValidation(valid=True, action=normalized)

    def _invalid(self, action: dict[str, Any], error: str, failure_class: str) -> ActionValidation:
        if self.metrics is not None:
            self.metrics.invalid_actions += 1
            self.metrics.replans += 1
        self._capture_failure(failure_class, error, action)
        return ActionValidation(valid=False, action=action, error=error, failure_class=failure_class)

    @staticmethod
    def action_signature(action: dict[str, Any]) -> str:
        payload = {
            "action": action.get("action"),
            "parameters": action.get("parameters") or {},
            "output": action.get("output"),
        }
        return _hash(payload)

    def record_action(self, action: dict[str, Any], result: Any, *, validation: ActionValidation | None = None) -> None:
        if self.metrics is None:
            return
        self.metrics.steps += 1
        signature = self.action_signature(action)
        failed = validation is not None and not validation.valid or _result_failed(result)
        if failed:
            self.failed_signatures[signature] += 1
            if validation is None or validation.valid:
                self.metrics.retries += 1
                self._capture_failure("ACTION_ERROR", str(result), action)
        name = str(action.get("action") or "").lower()
        if name == "speak_to_npc" and not failed:
            params = action.get("parameters") or {}
            target = str(next((params[key] for key in ("npc_name", "npc", "target", "name") if params.get(key)), ""))
            message = str(next((params[key] for key in ("message", "content", "text") if params.get(key)), ""))
            self.questions_asked.add((target, message))
        self.action_records.append(
            {
                "step": self.metrics.steps,
                "signature": signature,
                "action": _canonical(action),
                "result": _canonical(result),
                "failed": bool(failed),
            }
        )
        self.action_records = self.action_records[-50:]

    def _capture_failure(self, failure_class: str, error: str, action: Any) -> None:
        if self.first_failure is None:
            self.first_failure = {
                "step": (self.metrics.steps + 1) if self.metrics else 0,
                "error_type": failure_class,
                "message": str(error),
                "action": _canonical(action),
            }

    def prompt_context(self) -> dict[str, Any]:
        if self.metrics is None:
            return {}
        remaining = max(self.max_steps - self.metrics.steps, 0)
        ratio = remaining / self.max_steps
        phase = (
            "EARLY"
            if ratio > EARLY_PHASE_RATIO
            else "MID"
            if ratio > MID_PHASE_RATIO
            else "LATE"
            if remaining > CRITICAL_REMAINING_STEPS
            else "CRITICAL"
        )
        return {
            "task_type": self.task_type,
            "step_budget": {
                "current_step": self.metrics.steps,
                "max_steps": self.max_steps,
                "remaining_steps": remaining,
                "phase": phase,
            },
            "visible_object_ids": sorted(self.visible_object_ids),
            "observation_diff": self.last_observation_diff,
            "object_registry": {
                "unique_objects_seen": len(self.objects),
                "counts": self._count_summary(),
            },
            "npc": {
                "facts": self.npc_facts[-8:],
                "questions_asked": [list(item) for item in sorted(self.questions_asked)],
            },
            "recovery": {
                "stuck": self.metrics.stuck_count > 0,
                "blocked_failed_actions": sum(
                    1 for count in self.failed_signatures.values() if count >= self.repeated_action_limit
                ),
            },
        }

    def _count_summary(self) -> dict[str, dict[str, int]]:
        summary: dict[str, dict[str, int]] = {}
        for field_name in ("name", "semantic_type", "category", "type", "color", "shape"):
            counts: Counter[str] = Counter()
            for item in self.objects.values():
                value = item.get(field_name)
                if value not in (None, "", "Unknown", "unknown"):
                    counts[str(value)] += 1
            if counts:
                summary[field_name] = dict(sorted(counts.items()))
        return summary

    def finish(self, evaluation: Any = None, *, termination_reason: str = "evaluated") -> dict[str, Any] | None:
        if self.metrics is None:
            return None
        if isinstance(evaluation, dict):
            success_value = self._extract_success(evaluation)
            if success_value is not None:
                self.metrics.success = success_value
                self.metrics.verified = True
            score = _extract_numeric(evaluation, ("score", "total_score", "subject_score"))
            if score is not None:
                self.metrics.score = score
                self.metrics.verified = True
        self.metrics.termination_reason = termination_reason
        self.metrics.finished_at = datetime.now(timezone.utc).isoformat()
        self.metrics.latency = round(time.perf_counter() - self._started_monotonic, 6)
        payload = asdict(self.metrics)
        payload["evaluation"] = _canonical(evaluation)
        payload["world_state"] = {
            "known_objects": len(self.objects),
            "npc_facts": self.npc_facts,
            "recent_actions": self.action_records,
        }
        self._write_artifacts(payload)
        self.metrics = None
        return payload

    @staticmethod
    def _extract_success(value: Any) -> bool | None:
        if isinstance(value, dict):
            for key in ("success", "passed", "is_success", "completed"):
                if isinstance(value.get(key), bool):
                    return value[key]
            status = str(value.get("result") or value.get("status") or "").strip().lower()
            if status in {"success", "succeeded", "passed", "completed"}:
                return True
            if status in {"failed", "failure", "error"}:
                return False
            for child in value.values():
                found = CompetitionRuntime._extract_success(child)
                if found is not None:
                    return found
        if isinstance(value, list):
            for child in value:
                found = CompetitionRuntime._extract_success(child)
                if found is not None:
                    return found
        return None

    def _write_artifacts(self, payload: dict[str, Any]) -> None:
        metrics_dir = self.log_dir / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        episode_id = str(payload["episode_id"]).replace("/", "_").replace("\\", "_")
        self._atomic_json(metrics_dir / f"episode_{episode_id}.json", payload)
        if payload.get("success") is False or self.first_failure is not None:
            report = {
                "episode_id": payload["episode_id"],
                "task_type": payload["task_type"],
                "first_critical_error": self.first_failure,
                "cascade": "Subsequent actions may be degraded after the first critical error.",
                "could_succeed_if_fixed": self.first_failure is not None,
                "termination_reason": payload["termination_reason"],
            }
            self._atomic_json(metrics_dir / f"failure_{episode_id}.json", report)
            aggregate_path = metrics_dir / "failure_report.json"
            existing: list[Any] = []
            if aggregate_path.exists():
                try:
                    loaded = json.loads(aggregate_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, list):
                        existing = loaded
                except (OSError, json.JSONDecodeError):
                    existing = []
            existing = [item for item in existing if item.get("episode_id") != report["episode_id"]]
            existing.append(report)
            self._atomic_json(aggregate_path, existing)

    @staticmethod
    def _atomic_json(path: Path, payload: Any) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
