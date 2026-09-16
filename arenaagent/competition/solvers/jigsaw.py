from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median
from typing import Any

VECTOR_SIZE = 3
MIN_GRID_CENTERS = 2
BOUND_VALUE_COUNT = 4
ROTATION_CANDIDATES = (0, 90, 180, 270)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _position(item: dict[str, Any]) -> list[float] | None:
    value = item.get("position") or item.get("place_location") or item.get("location")
    if isinstance(value, dict):
        lowered = {str(key).lower(): raw for key, raw in value.items()}
        numbers = [_number(lowered.get(axis)) for axis in ("x", "y", "z")]
    elif isinstance(value, (list, tuple)) and len(value) >= VECTOR_SIZE:
        numbers = [_number(raw) for raw in value[:VECTOR_SIZE]]
    else:
        return None
    return [float(raw) for raw in numbers] if all(raw is not None for raw in numbers) else None


def _cluster(values: list[float], tolerance: float = 4.0) -> list[float]:
    centers: list[list[float]] = []
    for value in sorted(values):
        if not centers or abs(value - sum(centers[-1]) / len(centers[-1])) > tolerance:
            centers.append([value])
        else:
            centers[-1].append(value)
    return [round(sum(group) / len(group), 3) for group in centers]


def _uniform_centers(lower: float, upper: float, count: int) -> list[float]:
    width = upper - lower
    return [round(lower + width * (index + 0.5) / count, 3) for index in range(count)]


def _extend_centers(observed: list[float], lower: float, upper: float) -> list[float]:
    if len(observed) < MIN_GRID_CENTERS:
        return observed
    gaps = [right - left for left, right in zip(observed, observed[1:], strict=False) if right > left]
    if not gaps:
        return observed
    spacing = median(gaps)
    values = list(observed)
    while values[0] - spacing >= lower:
        values.insert(0, round(values[0] - spacing, 3))
    while values[-1] + spacing <= upper:
        values.append(round(values[-1] + spacing, 3))
    return values


@dataclass(slots=True)
class PieceState:
    object_id: str
    current_position: list[float] | None
    candidate_position: list[float] | None = None
    candidate_rotation: dict[str, float] | None = None
    placed: bool = False
    confidence: float = 0.0
    rotation_attempt: int = 0


@dataclass(slots=True)
class JigsawPlan:
    y_centers: list[float] = field(default_factory=list)
    z_centers: list[float] = field(default_factory=list)
    missing_cells: list[dict[str, float]] = field(default_factory=list)
    pieces: list[PieceState] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""

    def context(self) -> dict[str, Any]:
        return {
            "solver": "jigsaw_spatial_grid",
            "y_centers": self.y_centers,
            "z_centers": self.z_centers,
            "missing_cells": self.missing_cells,
            "pieces": [
                {
                    "object_id": piece.object_id,
                    "current_position": piece.current_position,
                    "candidate_position": piece.candidate_position,
                    "candidate_rotation": piece.candidate_rotation,
                    "placed": piece.placed,
                    "confidence": piece.confidence,
                    "rotation_attempt": piece.rotation_attempt,
                }
                for piece in self.pieces
            ],
            "candidate_yaw_degrees": list(ROTATION_CANDIDATES),
            "confidence": self.confidence,
            "reason": self.reason,
        }


class JigsawSpatialSolver:
    def infer(
        self,
        subject: dict[str, Any],
        objects: dict[str, dict[str, Any]],
        retry_counts: dict[str, int] | None = None,
    ) -> JigsawPlan:
        bounds = subject.get("reference_bounding")
        if not isinstance(bounds, (list, tuple)) or len(bounds) < BOUND_VALUE_COUNT:
            return JigsawPlan(reason="reference_bounding is unavailable")
        raw_bounds = [_number(value) for value in bounds[:BOUND_VALUE_COUNT]]
        if any(value is None for value in raw_bounds):
            return JigsawPlan(reason="reference_bounding contains non-numeric values")
        y_lower, y_upper = sorted((float(raw_bounds[0]), float(raw_bounds[2])))
        z_lower, z_upper = sorted((float(raw_bounds[1]), float(raw_bounds[3])))

        piece_ids = self._piece_ids(subject)
        piece_id_set = set(piece_ids)
        positions = {
            object_id: position
            for object_id, item in objects.items()
            if object_id not in piece_id_set
            if (position := _position(item)) is not None
            and y_lower <= position[1] <= y_upper
            and z_lower <= position[2] <= z_upper
        }
        observed_y = _cluster([position[1] for position in positions.values()])
        observed_z = _cluster([position[2] for position in positions.values()])
        rows = self._dimension(subject, "rows", "grid_rows", "row_count")
        columns = self._dimension(subject, "columns", "cols", "grid_cols", "column_count")
        y_centers = (
            _uniform_centers(y_lower, y_upper, columns) if columns else _extend_centers(observed_y, y_lower, y_upper)
        )
        z_centers = _uniform_centers(z_lower, z_upper, rows) if rows else _extend_centers(observed_z, z_lower, z_upper)
        if not y_centers or not z_centers:
            return JigsawPlan(
                y_centers=y_centers,
                z_centers=z_centers,
                reason="not enough public coordinates to infer a grid",
            )

        occupied = {
            (self._nearest(position[1], y_centers), self._nearest(position[2], z_centers))
            for position in positions.values()
        }
        x_plane = round(median(position[0] for position in positions.values()), 3) if positions else None
        missing = [
            {"y": y_value, "z": z_value}
            for z_value in z_centers
            for y_value in y_centers
            if (y_value, z_value) not in occupied
        ]
        retry_counts = retry_counts or {}
        pieces = [
            PieceState(
                object_id=value,
                current_position=_position(objects.get(value, {})),
                rotation_attempt=max(int(retry_counts.get(value, 0)), 0),
            )
            for value in piece_ids
        ]
        for piece, cell in zip(pieces, missing, strict=False):
            if x_plane is not None:
                piece.candidate_position = [x_plane, cell["y"], cell["z"]]
                yaw = ROTATION_CANDIDATES[piece.rotation_attempt % len(ROTATION_CANDIDATES)]
                piece.candidate_rotation = {"roll": 0.0, "yaw": float(yaw), "pitch": 0.0}
                piece.confidence = 0.8 if rows and columns else 0.55
        enough_observed_centers = len(observed_y) >= MIN_GRID_CENTERS and len(observed_z) >= MIN_GRID_CENTERS
        confidence = 0.9 if rows and columns else 0.6 if enough_observed_centers else 0.35
        return JigsawPlan(
            y_centers=y_centers,
            z_centers=z_centers,
            missing_cells=missing,
            pieces=pieces,
            confidence=confidence,
            reason=(
                "grid and placement plane inferred from reference bounds and public object positions"
                if x_plane is not None
                else "grid inferred, but no public X-plane evidence exists for a safe placement coordinate"
            ),
        )

    @staticmethod
    def _dimension(subject: dict[str, Any], *keys: str) -> int | None:
        for key in keys:
            value = subject.get(key)
            number = _number(value)
            if number is not None and int(number) > 0:
                return int(number)
        return None

    @staticmethod
    def _nearest(value: float, candidates: list[float]) -> float:
        return min(candidates, key=lambda candidate: abs(candidate - value))

    @staticmethod
    def _piece_ids(subject: dict[str, Any]) -> list[str]:
        raw = subject.get("piece_object_id") or subject.get("movable_object_id") or []
        values = raw if isinstance(raw, (list, tuple, set)) else [raw]
        return [str(value) for value in values if value not in (None, "")]
