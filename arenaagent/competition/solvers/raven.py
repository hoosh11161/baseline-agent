from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
from PIL import Image

FEATURE_NAMES = ("count", "fill", "x", "y", "orientation", "size", "symmetry_h", "symmetry_v")
MAX_RULE_HYPOTHESES = 12
MASK_SIZE = 64
PROBLEM_PANEL_COUNT = 8
RGB_DIMENSIONS = 3
RULE_FIT_THRESHOLD = 0.8
NUMERIC_ERROR_THRESHOLD = 0.12
NUMERIC_CONSISTENCY_THRESHOLD = 0.88
MAX_FOREGROUND_RATIO = 0.5
MIN_COMPONENT_AREA = 4


@dataclass(slots=True, frozen=True)
class RuleHypothesis:
    axis: str
    feature: str
    rule: str
    coverage_score: float
    consistency_score: float
    complexity_penalty: float

    def context(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "feature": self.feature,
            "rule": self.rule,
            "coverage_score": round(self.coverage_score, 6),
            "consistency_score": round(self.consistency_score, 6),
            "complexity_penalty": round(self.complexity_penalty, 6),
        }


@dataclass(slots=True)
class RavenVerification:
    candidate_scores: list[float]
    hypotheses: list[RuleHypothesis] = field(default_factory=list)
    confidence: float = 0.0

    def context(self) -> dict[str, Any]:
        ranked = sorted(enumerate(self.candidate_scores, start=1), key=lambda item: (-item[1], item[0]))
        return {
            "candidate_scores": [round(value, 6) for value in self.candidate_scores],
            "ranked_candidates": [index for index, _ in ranked],
            "confidence": round(self.confidence, 6),
            "hypotheses": [item.context() for item in self.hypotheses],
        }


@dataclass(slots=True)
class RavenDecision:
    candidates: list[list[int]]
    scores: list[float]
    answer: list[int]
    confidence: float
    margin: float
    low_confidence: bool
    rule_verification: list[RavenVerification] = field(default_factory=list)

    @classmethod
    def from_ranked(
        cls,
        candidates: list[list[int]],
        scores: list[float] | None = None,
        *,
        low_confidence_threshold: float = 0.15,
        rule_verification: list[RavenVerification] | None = None,
    ) -> RavenDecision | None:
        if not candidates:
            return None
        normalized_scores = [float(value) for value in (scores or []) if math.isfinite(float(value))]
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
            rule_verification=list(rule_verification or []),
        )

    def context(self, attempt_index: int = 0) -> dict[str, Any]:
        used_index = min(max(int(attempt_index), 0), len(self.candidates) - 1)
        return {
            "solver": "local_resnet18_mlp_with_rule_verification",
            "candidate_count": len(self.candidates),
            "attempt_index": used_index,
            "answer": self.candidates[used_index],
            "top_confidence": round(self.confidence, 6),
            "top_margin": round(self.margin, 6),
            "low_confidence": self.low_confidence,
            "rule_verification": [item.context() for item in self.rule_verification],
            "fallback_policy": "try at most three ranked candidates after official rejection",
        }


class RavenRuleVerifier:
    """Verify simple Raven rules against two complete public rows/columns."""

    _NUMERIC_RULES: dict[str, tuple[Callable[[float, float], float], float]] = {
        "alternation": (lambda left, _middle: left, 0.02),
        "progression": (lambda left, middle: 2.0 * middle - left, 0.08),
        "sum": (lambda left, middle: left + middle, 0.1),
        "difference": (lambda left, middle: abs(left - middle), 0.1),
        "mean": (lambda left, middle: (left + middle) / 2.0, 0.12),
    }
    _MASK_RULES: dict[str, tuple[Callable[[np.ndarray, np.ndarray], np.ndarray], float]] = {
        "union": (np.logical_or, 0.05),
        "intersection": (np.logical_and, 0.05),
        "xor": (np.logical_xor, 0.12),
        "difference": (lambda left, middle: np.logical_and(left, np.logical_not(middle)), 0.1),
    }

    def verify(self, problem_panels: list[Any], answer_panels: list[Any]) -> RavenVerification | None:
        if len(problem_panels) < PROBLEM_PANEL_COUNT or not answer_panels:
            return None
        try:
            problem_masks = [self._mask(panel) for panel in problem_panels[:8]]
            answer_masks = [self._mask(panel) for panel in answer_panels]
        except (TypeError, ValueError):
            return None
        problem_features = [self._features(mask) for mask in problem_masks]
        answer_features = [self._features(mask) for mask in answer_masks]
        hypotheses: list[RuleHypothesis] = []
        scorers: list[Callable[[np.ndarray, dict[str, float]], float]] = []

        layouts = {
            "row": ((0, 1, 2), (3, 4, 5), (6, 7)),
            "column": ((0, 3, 6), (1, 4, 7), (2, 5)),
        }
        for axis, (known_a, known_b, target_pair) in layouts.items():
            mask_hypotheses, mask_scorers = self._mask_hypotheses(
                axis, problem_masks, known_a, known_b, target_pair
            )
            hypotheses.extend(mask_hypotheses)
            scorers.extend(mask_scorers)
            numeric_hypotheses, numeric_scorers = self._numeric_hypotheses(
                axis, problem_features, known_a, known_b, target_pair
            )
            hypotheses.extend(numeric_hypotheses)
            scorers.extend(numeric_scorers)

        ranked_pairs = sorted(
            zip(hypotheses, scorers, strict=False),
            key=lambda pair: (-(pair[0].coverage_score + pair[0].consistency_score - pair[0].complexity_penalty)),
        )[:MAX_RULE_HYPOTHESES]
        if not ranked_pairs:
            return RavenVerification([0.0 for _ in answer_masks])
        kept_hypotheses = [item[0] for item in ranked_pairs]
        kept_scorers = [item[1] for item in ranked_pairs]
        candidate_scores = [
            float(np.mean([scorer(mask, features) for scorer in kept_scorers]))
            for mask, features in zip(answer_masks, answer_features, strict=False)
        ]
        ordered = sorted(candidate_scores, reverse=True)
        confidence = max(ordered[0] - ordered[1], 0.0) if len(ordered) > 1 else ordered[0]
        return RavenVerification(candidate_scores, kept_hypotheses, confidence)

    def _mask_hypotheses(
        self,
        axis: str,
        masks: list[np.ndarray],
        known_a: tuple[int, int, int],
        known_b: tuple[int, int, int],
        target_pair: tuple[int, int],
    ) -> tuple[list[RuleHypothesis], list[Callable[[np.ndarray, dict[str, float]], float]]]:
        hypotheses: list[RuleHypothesis] = []
        scorers: list[Callable[[np.ndarray, dict[str, float]], float]] = []
        for rule_name, (operation, penalty) in self._MASK_RULES.items():
            fit_a = self._iou(operation(masks[known_a[0]], masks[known_a[1]]), masks[known_a[2]])
            fit_b = self._iou(operation(masks[known_b[0]], masks[known_b[1]]), masks[known_b[2]])
            consistency = (fit_a + fit_b) / 2.0
            coverage = sum(value >= RULE_FIT_THRESHOLD for value in (fit_a, fit_b)) / 2.0
            if coverage < 1.0 or consistency < RULE_FIT_THRESHOLD:
                continue
            expected = operation(masks[target_pair[0]], masks[target_pair[1]])
            hypotheses.append(RuleHypothesis(axis, "shape_mask", rule_name, coverage, consistency, penalty))
            scorers.append(lambda candidate, _features, expected=expected: self._iou(expected, candidate))
        return hypotheses, scorers

    def _numeric_hypotheses(
        self,
        axis: str,
        features: list[dict[str, float]],
        known_a: tuple[int, int, int],
        known_b: tuple[int, int, int],
        target_pair: tuple[int, int],
    ) -> tuple[list[RuleHypothesis], list[Callable[[np.ndarray, dict[str, float]], float]]]:
        hypotheses: list[RuleHypothesis] = []
        scorers: list[Callable[[np.ndarray, dict[str, float]], float]] = []
        for feature_name in FEATURE_NAMES:
            for rule_name, (operation, penalty) in self._NUMERIC_RULES.items():
                errors: list[float] = []
                for line in (known_a, known_b):
                    predicted = operation(features[line[0]][feature_name], features[line[1]][feature_name])
                    actual = features[line[2]][feature_name]
                    errors.append(self._relative_error(predicted, actual))
                consistency = max(1.0 - float(np.mean(errors)), 0.0)
                coverage = sum(error <= NUMERIC_ERROR_THRESHOLD for error in errors) / 2.0
                if coverage < 1.0 or consistency < NUMERIC_CONSISTENCY_THRESHOLD:
                    continue
                expected = operation(
                    features[target_pair[0]][feature_name], features[target_pair[1]][feature_name]
                )
                hypotheses.append(
                    RuleHypothesis(axis, feature_name, rule_name, coverage, consistency, penalty)
                )
                scorers.append(
                    lambda _candidate, candidate_features, expected=expected, name=feature_name: max(
                        1.0 - self._relative_error(expected, candidate_features[name]), 0.0
                    )
                )
        return hypotheses, scorers

    @staticmethod
    def _mask(panel: Any) -> np.ndarray:
        if hasattr(panel, "convert"):
            panel = panel.convert("L").resize((MASK_SIZE, MASK_SIZE))
        array = np.asarray(panel, dtype=np.float32)
        if array.ndim == RGB_DIMENSIONS:
            array = array.mean(axis=2)
        if array.shape != (MASK_SIZE, MASK_SIZE):
            array = np.asarray(Image.fromarray(array.astype(np.uint8)).resize((MASK_SIZE, MASK_SIZE)))
        threshold = min(float(np.median(array)), 220.0)
        mask = array < threshold
        if float(mask.mean()) > MAX_FOREGROUND_RATIO:
            mask = np.logical_not(mask)
        return mask

    @classmethod
    def _features(cls, mask: np.ndarray) -> dict[str, float]:
        points = np.argwhere(mask)
        if not len(points):
            return {name: 0.0 for name in FEATURE_NAMES}
        y_values = points[:, 0]
        x_values = points[:, 1]
        x_center = float(x_values.mean() / max(mask.shape[1] - 1, 1))
        y_center = float(y_values.mean() / max(mask.shape[0] - 1, 1))
        width = int(x_values.max() - x_values.min() + 1)
        height = int(y_values.max() - y_values.min() + 1)
        centered = np.column_stack((x_values - x_values.mean(), y_values - y_values.mean()))
        covariance = np.cov(centered, rowvar=False) if len(centered) > 1 else np.zeros((2, 2))
        orientation = 0.5 * math.atan2(2 * covariance[0, 1], covariance[0, 0] - covariance[1, 1])
        return {
            "count": float(cls._component_count(mask)),
            "fill": float(mask.mean()),
            "x": x_center,
            "y": y_center,
            "orientation": float((orientation + math.pi / 2.0) / math.pi),
            "size": float(width * height / mask.size),
            "symmetry_h": cls._iou(mask, np.fliplr(mask)),
            "symmetry_v": cls._iou(mask, np.flipud(mask)),
        }

    @staticmethod
    def _component_count(mask: np.ndarray) -> int:
        visited = np.zeros_like(mask, dtype=bool)
        count = 0
        height, width = mask.shape
        for y_coord, x_coord in np.argwhere(mask):
            if visited[y_coord, x_coord]:
                continue
            stack = [(int(y_coord), int(x_coord))]
            visited[y_coord, x_coord] = True
            area = 0
            while stack:
                y_value, x_value = stack.pop()
                area += 1
                for next_y, next_x in (
                    (y_value - 1, x_value),
                    (y_value + 1, x_value),
                    (y_value, x_value - 1),
                    (y_value, x_value + 1),
                ):
                    if (
                        0 <= next_y < height
                        and 0 <= next_x < width
                        and mask[next_y, next_x]
                        and not visited[next_y, next_x]
                    ):
                        visited[next_y, next_x] = True
                        stack.append((next_y, next_x))
            if area >= MIN_COMPONENT_AREA:
                count += 1
        return count

    @staticmethod
    def _iou(left: np.ndarray, right: np.ndarray) -> float:
        union = np.logical_or(left, right).sum()
        if not union:
            return 1.0
        return float(np.logical_and(left, right).sum() / union)

    @staticmethod
    def _relative_error(predicted: float, actual: float) -> float:
        scale = max(abs(predicted), abs(actual), 0.05)
        return min(abs(predicted - actual) / scale, 1.0)
