from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

COUNT_WORDS = ("多少", "几个", "数量", "count", "howmany", "numberof")
GROUP_WORDS = ("分别", "各有", "各自", "respectively", "each")
FIELD_NAMES = ("name", "semantic_type", "category", "type", "color", "shape")

VALUE_ALIASES: dict[str, tuple[str, ...]] = {
    "red": ("red", "红", "红色"),
    "blue": ("blue", "蓝", "蓝色"),
    "green": ("green", "绿", "绿色"),
    "yellow": ("yellow", "黄", "黄色"),
    "black": ("black", "黑", "黑色"),
    "white": ("white", "白", "白色"),
    "orange": ("orange", "橙", "橙色"),
    "purple": ("purple", "紫", "紫色"),
    "pink": ("pink", "粉", "粉色"),
    "gray": ("gray", "grey", "灰", "灰色"),
    "cuboid": ("cuboid", "cube", "box", "立方体", "长方体", "方块"),
    "sphere": ("sphere", "ball", "球", "球体"),
    "cylinder": ("cylinder", "圆柱", "圆柱体"),
    "cone": ("cone", "圆锥", "圆锥体"),
}


def _normalize(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").lower())


def _aliases(value: str) -> set[str]:
    normalized = _normalize(value)
    aliases = {_normalize(alias) for alias in VALUE_ALIASES.get(normalized, ())}
    aliases.add(normalized)
    return {alias for alias in aliases if alias}


@dataclass(slots=True, frozen=True)
class CountFilter:
    field: str
    value: str


@dataclass(slots=True)
class CountingResult:
    confident: bool
    answer: int | None
    grouped_counts: dict[str, int] = field(default_factory=dict)
    matched_ids: list[str] = field(default_factory=list)
    filters: list[CountFilter] = field(default_factory=list)
    reason: str = ""

    def context(self) -> dict[str, Any]:
        return {
            "confident": self.confident,
            "answer": self.answer,
            "grouped_counts": self.grouped_counts,
            "matched_ids": self.matched_ids,
            "filters": [{"field": item.field, "value": item.value} for item in self.filters],
            "reason": self.reason,
        }


class CountingSolver:
    """Deterministic registry counter with bounded viewpoint exploration."""

    def __init__(self, scan_degrees: list[float] | None = None) -> None:
        self.scan_degrees = [float(value) for value in (scan_degrees or [90.0, 180.0, 270.0])]
        self.episode_id = ""
        self.attempted_degrees: list[float] = []
        self.observation_count = 0
        self.last_result: CountingResult | None = None

    def reset(self, episode_id: str) -> None:
        self.episode_id = str(episode_id)
        self.attempted_degrees = []
        self.observation_count = 0
        self.last_result = None

    def observe(self, episode_id: str) -> None:
        if self.episode_id != str(episode_id):
            self.reset(str(episode_id))
        self.observation_count += 1

    @property
    def coverage_complete(self) -> bool:
        return len(self.attempted_degrees) >= len(self.scan_degrees)

    def next_scan_action(self) -> dict[str, Any] | None:
        if self.coverage_complete:
            return None
        degree = self.scan_degrees[len(self.attempted_degrees)]
        self.attempted_degrees.append(degree)
        return {
            "think": "bounded counting scan",
            "action": "turn_in_degree",
            "parameters": {"degree": degree},
            "output": 0,
        }

    def solve(self, query: str, objects: dict[str, dict[str, Any]]) -> CountingResult:
        normalized_query = _normalize(query)
        if not any(_normalize(word) in normalized_query for word in COUNT_WORDS):
            result = CountingResult(False, None, reason="query is not a recognized counting question")
            self.last_result = result
            return result

        filters = self._filters_from_query(normalized_query, objects)
        grouped = any(_normalize(word) in normalized_query for word in GROUP_WORDS)
        if not filters:
            matched_ids = sorted(objects)
            result = CountingResult(
                True,
                len(matched_ids),
                grouped_counts={"all": len(matched_ids)},
                matched_ids=matched_ids,
                reason="counted all deduplicated registry objects",
            )
            self._mark_counted(objects, matched_ids)
            self.last_result = result
            return result

        grouped_counts = {
            f"{item.field}={item.value}": sum(self._matches(obj, [item]) for obj in objects.values())
            for item in filters
        }
        matched_ids = sorted(object_id for object_id, obj in objects.items() if self._matches(obj, filters))
        answer = None if grouped else len(matched_ids)
        reason = (
            "multiple requested groups require evaluator-specific output formatting"
            if grouped
            else "computed from deduplicated registry with all requested attributes"
        )
        result = CountingResult(
            confident=not grouped,
            answer=answer,
            grouped_counts=grouped_counts,
            matched_ids=matched_ids,
            filters=filters,
            reason=reason,
        )
        self._mark_counted(objects, matched_ids)
        self.last_result = result
        return result

    @staticmethod
    def _mark_counted(objects: dict[str, dict[str, Any]], matched_ids: list[str]) -> None:
        for object_id, item in objects.items():
            item["counted"] = object_id in matched_ids

    @staticmethod
    def _matches(obj: dict[str, Any], filters: list[CountFilter]) -> bool:
        alternatives_by_field: dict[str, set[str]] = {}
        for item in filters:
            alternatives_by_field.setdefault(item.field, set()).add(_normalize(item.value))
        for field_name, accepted_values in alternatives_by_field.items():
            actual = _normalize(obj.get(field_name))
            if actual not in accepted_values:
                return False
        return True

    @staticmethod
    def _filters_from_query(query: str, objects: dict[str, dict[str, Any]]) -> list[CountFilter]:
        found: list[CountFilter] = []
        seen: set[tuple[str, str]] = set()
        for field_name in FIELD_NAMES:
            values = sorted(
                {
                    str(item[field_name])
                    for item in objects.values()
                    if item.get(field_name) not in (None, "", "Unknown", "unknown")
                }
            )
            for value in values:
                if not any(alias in query for alias in _aliases(value)):
                    continue
                key = (field_name, _normalize(value))
                if key not in seen:
                    found.append(CountFilter(field_name, value))
                    seen.add(key)
        return found
