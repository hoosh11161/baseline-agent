from __future__ import annotations

from typing import Any

from arenaagent.competition.runtime import CompetitionRuntime
from arenaagent.competition.solvers.counting import CountingSolver
from arenaagent.competition.solvers.jigsaw import JigsawSpatialSolver

JIGSAW_AUTO_PLACEMENT_CONFIDENCE = 0.8
VECTOR_DIMENSIONS = 3


def _task_text(subject: Any) -> str:
    if isinstance(subject, dict):
        return str(subject.get("subject") or subject.get("goal") or subject.get("task_prompt") or "")
    return str(subject or "")


class TaskStrategyRouter:
    """Route public task observations to bounded task-specific strategies."""

    def __init__(self, *, counting_scan_degrees: list[float] | None = None) -> None:
        self.counting = CountingSolver(counting_scan_degrees)
        self.jigsaw = JigsawSpatialSolver()

    def observe(self, runtime: CompetitionRuntime, subject: Any = None) -> None:
        if runtime.metrics is None:
            return
        if runtime.task_type == "counting":
            self.counting.observe(runtime.metrics.episode_id)
        elif runtime.task_type == "jigsaw" and isinstance(subject, dict):
            runtime.set_strategy_context(
                self.jigsaw.infer(
                    subject,
                    runtime.objects,
                    dict(runtime.progress.retries),
                    set(runtime.progress.completed_objects),
                ).context()
            )

    def propose_action(self, subject: Any, runtime: CompetitionRuntime) -> dict[str, Any] | None:
        if runtime.metrics is None:
            return None
        if runtime.task_type == "jigsaw":
            return self._propose_jigsaw_placement(runtime)
        if runtime.task_type != "counting":
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

    @staticmethod
    def _propose_jigsaw_placement(runtime: CompetitionRuntime) -> dict[str, Any] | None:
        """Use a complete high-confidence public grid plan without another VLM transcription."""
        held_piece = runtime.progress.current_object
        if not held_piece or runtime.progress.pending_pick or runtime.progress.pending_place:
            return None
        strategy = runtime.strategy_context
        if (
            strategy.get("solver") != "jigsaw_spatial_grid"
            or float(strategy.get("confidence") or 0) < JIGSAW_AUTO_PLACEMENT_CONFIDENCE
        ):
            return None
        pieces = strategy.get("pieces")
        if not isinstance(pieces, list):
            return None
        piece = next(
            (
                item
                for item in pieces
                if isinstance(item, dict)
                and str(item.get("object_id")) == held_piece
                and float(item.get("confidence") or 0) >= JIGSAW_AUTO_PLACEMENT_CONFIDENCE
            ),
            None,
        )
        if piece is None:
            return None
        location = piece.get("candidate_position")
        rotation = piece.get("candidate_rotation")
        if not isinstance(location, list) or len(location) < VECTOR_DIMENSIONS or not isinstance(rotation, dict):
            return None
        return {
            "think": "high-confidence public jigsaw grid placement",
            "action": "put_down_sth",
            "parameters": {
                "target_location": location,
                "target_rotation": rotation,
                "auto_rotate": False,
            },
            "output": 0,
            "expected_change": f"piece {held_piece} leaves the hand at the inferred empty cell",
        }
