"""Task-specific competition solvers."""

from arenaagent.competition.solvers.counting import CountingResult, CountingSolver
from arenaagent.competition.solvers.jigsaw import JigsawPlan, JigsawSpatialSolver, PieceState
from arenaagent.competition.solvers.npc import NPCMemory
from arenaagent.competition.solvers.raven import RavenDecision
from arenaagent.competition.solvers.tidyroom import TidyRoomTracker

__all__ = [
    "CountingResult",
    "CountingSolver",
    "JigsawPlan",
    "JigsawSpatialSolver",
    "NPCMemory",
    "PieceState",
    "RavenDecision",
    "TidyRoomTracker",
]
