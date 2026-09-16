from __future__ import annotations

from typing import Any

from arenaagent.competition.runtime import CompetitionRuntime
from arenaagent.competition.solvers.counting import CountingSolver


def _task_text(subject: Any) -> str:
    if isinstance(subject, dict):
        return str(subject.get("subject") or subject.get("goal") or subject.get("task_prompt") or "")
    return str(subject or "")


class TaskStrategyRouter:
    """Route public task observations to bounded task-specific strategies."""

    def __init__(self, *, counting_scan_degrees: list[float] | None = None) -> None:
        self.counting = CountingSolver(counting_scan_degrees)

    def observe(self, runtime: CompetitionRuntime) -> None:
        if runtime.metrics is None:
            return
        if runtime.task_type == "counting":
            self.counting.observe(runtime.metrics.episode_id)

    def propose_action(self, subject: Any, runtime: CompetitionRuntime) -> dict[str, Any] | None:
        if runtime.task_type != "counting" or runtime.metrics is None:
            return None
        scan_action = self.counting.next_scan_action()
        if scan_action is not None:
            runtime.set_strategy_context(
                {
                    "name": "counting",
                    "mode": "systematic_scan",
                    "observation_count": self.counting.observation_count,
                    "attempted_degrees": self.counting.attempted_degrees,
                    "coverage_complete": False,
                }
            )
            return scan_action

        result = self.counting.solve(_task_text(subject), runtime.objects)
        runtime.set_strategy_context(
            {
                "name": "counting",
                "mode": "deterministic_count",
                "observation_count": self.counting.observation_count,
                "attempted_degrees": self.counting.attempted_degrees,
                "coverage_complete": True,
                "result": result.context(),
            }
        )
        if not result.confident or result.answer is None:
            return None
        return {
            "think": "deterministic deduplicated count",
            "action": "submit_answer",
            "parameters": {},
            "output": result.answer,
        }
