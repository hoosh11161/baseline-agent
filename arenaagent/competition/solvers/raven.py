from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RavenDecision:
    candidates: list[list[int]]
    scores: list[float]
    answer: list[int]
    confidence: float
    margin: float
    low_confidence: bool

    @classmethod
    def from_ranked(
        cls,
        candidates: list[list[int]],
        scores: list[float] | None = None,
        *,
        low_confidence_threshold: float = 0.15,
    ) -> "RavenDecision | None":
        if not candidates:
            return None
        normalized_scores = [float(value) for value in (scores or [])]
        confidence = normalized_scores[0] if normalized_scores else 0.0
        second = normalized_scores[1] if len(normalized_scores) > 1 else 0.0
        margin = max(confidence - second, 0.0)
        return cls(
            candidates=candidates,
            scores=normalized_scores,
            answer=candidates[0],
            confidence=confidence,
            margin=margin,
            low_confidence=not normalized_scores or confidence < low_confidence_threshold,
        )

    def context(self, attempt_index: int = 0) -> dict[str, Any]:
        used_index = min(max(int(attempt_index), 0), len(self.candidates) - 1)
        return {
            "solver": "local_resnet18_mlp",
            "candidate_count": len(self.candidates),
            "attempt_index": used_index,
            "answer": self.candidates[used_index],
            "top_confidence": round(self.confidence, 6),
            "top_margin": round(self.margin, 6),
            "low_confidence": self.low_confidence,
            "fallback_policy": "try at most three ranked candidates after official rejection",
        }
