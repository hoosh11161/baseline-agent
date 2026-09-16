from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from arenaagent.competition.runtime import CompetitionRuntime


@dataclass(slots=True)
class ReplayStep:
    step: int
    valid: bool
    expected_valid: bool | None
    matched_expectation: bool
    failure_class: str
    error: str


def replay_public_trace(trace: dict[str, Any], *, log_dir: str | Path) -> dict[str, Any]:
    """Replay public observations/actions through the local competition guards.

    The trace contains only values available to an agent at runtime. It does
    not infer evaluator state, execute TongSIM actions, or claim task success.
    """
    subject = trace.get("subject")
    if not isinstance(subject, dict):
        raise ValueError("trace.subject must be an object")
    raw_steps = trace.get("steps")
    if not isinstance(raw_steps, list):
        raise ValueError("trace.steps must be a list")

    runtime = CompetitionRuntime(
        log_dir=str(log_dir),
        repeated_action_limit=int(trace.get("repeated_action_limit", 2)),
        stagnant_observation_limit=int(trace.get("stagnant_observation_limit", 5)),
    )
    runtime.ensure_episode(subject)
    outcomes: list[ReplayStep] = []
    for index, raw_step in enumerate(raw_steps, start=1):
        if not isinstance(raw_step, dict):
            raise ValueError(f"trace.steps[{index - 1}] must be an object")
        before = bool(raw_step.get("object_in_hand_before", False))
        runtime.update_hand_state(before)
        runtime.observe(raw_step.get("visible_objects", []), raw_step.get("task_response"))
        action = raw_step.get("action")
        decision = runtime.validate_action(action, object_in_hand=before)
        expected = raw_step.get("expected_valid")
        expected_valid = expected if isinstance(expected, bool) else None
        matched = expected_valid is None or expected_valid == decision.valid
        outcomes.append(
            ReplayStep(
                step=index,
                valid=decision.valid,
                expected_valid=expected_valid,
                matched_expectation=matched,
                failure_class=decision.failure_class,
                error=decision.error,
            )
        )
        runtime.record_action(
            decision.action,
            raw_step.get("result", {"result": "success" if decision.valid else "failed"}),
            validation=decision,
        )
        if "object_in_hand_after" in raw_step:
            runtime.update_hand_state(bool(raw_step["object_in_hand_after"]))

    mismatches = [asdict(outcome) for outcome in outcomes if not outcome.matched_expectation]
    metrics = asdict(runtime.metrics) if runtime.metrics else {}
    for volatile_field in ("started_at", "finished_at", "latency"):
        metrics.pop(volatile_field, None)
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "verification_scope": "OFFLINE_PUBLIC_TRACE_GUARD_REPLAY",
        "official_score_verified": False,
        "task_type": runtime.task_type,
        "steps": [asdict(outcome) for outcome in outcomes],
        "mismatches": mismatches,
        "metrics": metrics,
    }
