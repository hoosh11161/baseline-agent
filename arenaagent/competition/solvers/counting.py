from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from typing import Any

COUNT_WORDS = ("多少", "几个", "数量", "count", "how many", "number of")
GROUP_WORDS = ("分别", "各有", "各自", "respectively", "each")
TOTAL_WORDS = ("一共", "总共", "全部", "总计", "total", "altogether")
FIELD_NAMES = (
    "name",
    "semantic_type",
    "category",
    "type",
    "color",
    "shape",
    "support_surface",
    "parent_surface",
    "container",
    "room",
    "location_name",
)
GROUP_SEPARATORS = r"(?:和|以及|及|、|与|and)"
MIN_GROUP_SEGMENTS = 2

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
    "cup": ("cup", "杯", "杯子", "水杯"),
    "plate": ("plate", "盘", "盘子"),
    "bowl": ("bowl", "碗"),
    "table": ("table", "桌", "桌子", "餐桌"),
    "desk": ("desk", "书桌"),
    "shelf": ("shelf", "架", "架子", "货架"),
}


def _normalize(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").lower())


def _aliases(value: str) -> set[str]:
    normalized = _normalize(value)
    aliases = {_normalize(alias) for alias in VALUE_ALIASES.get(normalized, ())}
    aliases.add(normalized)
    return {alias for alias in aliases if alias}


def _alias_is_present(alias: str, raw_query: str, normalized_query: str) -> bool:
    if not alias:
        return False
    if re.fullmatch(r"[a-z0-9]+", alias):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", raw_query.lower()))
    return alias in normalized_query


@dataclass(slots=True, frozen=True)
class CountFilter:
    field: str
    value: str

    @property
    def label(self) -> str:
        return f"{self.field}={self.value}"


@dataclass(slots=True)
class FilterExpression:
    """Small DNF expression: OR(AND(clause), ...), followed by NOT filters."""

    clauses: list[list[CountFilter]] = field(default_factory=list)
    exclusions: list[CountFilter] = field(default_factory=list)

    def matches(self, obj: dict[str, Any]) -> bool:
        positive = not self.clauses or any(
            all(_matches_filter(obj, item) for item in clause) for clause in self.clauses
        )
        excluded = any(_matches_filter(obj, item) for item in self.exclusions)
        return positive and not excluded

    def context(self) -> dict[str, Any]:
        return {
            "operator": "AND_NOT",
            "include": {
                "operator": "OR",
                "clauses": [
                    {"operator": "AND", "filters": [item.label for item in clause]} for clause in self.clauses
                ],
            },
            "exclude": {"operator": "OR", "filters": [item.label for item in self.exclusions]},
        }


def _matches_filter(obj: dict[str, Any], item: CountFilter) -> bool:
    actual = _normalize(obj.get(item.field))
    return actual == _normalize(item.value)


@dataclass(slots=True)
class CountingResult:
    confident: bool
    answer: int | None
    grouped_counts: dict[str, int] = field(default_factory=dict)
    matched_ids: list[str] = field(default_factory=list)
    filters: list[CountFilter] = field(default_factory=list)
    expression: FilterExpression | None = None
    reason: str = ""

    def context(self) -> dict[str, Any]:
        return {
            "confident": self.confident,
            "answer": self.answer,
            "grouped_counts": self.grouped_counts,
            "matched_ids": self.matched_ids,
            "filters": [{"field": item.field, "value": item.value} for item in self.filters],
            "expression": self.expression.context() if self.expression else None,
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
        raw_query = str(query or "")
        normalized_query = _normalize(raw_query)
        if not any(_normalize(word) in normalized_query for word in COUNT_WORDS):
            result = CountingResult(False, None, reason="query is not a recognized counting question")
            self.last_result = result
            return result

        filters = self._filters_from_query(raw_query, objects)
        grouped = any(_normalize(word) in normalized_query for word in GROUP_WORDS)
        expression, grouped_clauses = self._build_expression(raw_query, filters, grouped)
        matched_ids = sorted(object_id for object_id, obj in objects.items() if expression.matches(obj))

        if grouped and grouped_clauses:
            grouped_counts = {
                self._clause_label(clause): sum(
                    all(_matches_filter(obj, item) for item in clause) for obj in objects.values()
                )
                for clause in grouped_clauses
            }
            result = CountingResult(
                confident=False,
                answer=None,
                grouped_counts=grouped_counts,
                matched_ids=matched_ids,
                filters=filters,
                expression=expression,
                reason="explicit groups were evaluated independently; output formatting remains evaluator-specific",
            )
        else:
            reason = (
                "counted all deduplicated registry objects"
                if not filters
                else "evaluated a deterministic AND/OR/NOT filter expression over the deduplicated registry"
            )
            result = CountingResult(
                confident=True,
                answer=len(matched_ids),
                grouped_counts={"all": len(matched_ids)},
                matched_ids=matched_ids,
                filters=filters,
                expression=expression,
                reason=reason,
            )
        self._mark_counted(objects, matched_ids)
        self.last_result = result
        return result

    @staticmethod
    def _clause_label(clause: list[CountFilter]) -> str:
        return "&".join(item.label for item in clause) or "all"

    @staticmethod
    def _mark_counted(objects: dict[str, dict[str, Any]], matched_ids: list[str]) -> None:
        for object_id, item in objects.items():
            item["counted"] = object_id in matched_ids

    @classmethod
    def _build_expression(
        cls, raw_query: str, filters: list[CountFilter], grouped: bool
    ) -> tuple[FilterExpression, list[list[CountFilter]]]:
        exclusions = [item for item in filters if cls._is_negated(raw_query, item)]
        positives = [item for item in filters if item not in exclusions]
        grouped_clauses = cls._grouped_clauses(raw_query, positives) if grouped else []
        if grouped_clauses:
            return FilterExpression(clauses=grouped_clauses, exclusions=exclusions), grouped_clauses

        alternatives_by_field: dict[str, list[CountFilter]] = {}
        for item in positives:
            alternatives_by_field.setdefault(item.field, []).append(item)
        if not alternatives_by_field:
            clauses: list[list[CountFilter]] = [[]]
        else:
            clauses = [list(values) for values in itertools.product(*alternatives_by_field.values())]
        return FilterExpression(clauses=clauses, exclusions=exclusions), []

    @staticmethod
    def _is_negated(raw_query: str, item: CountFilter) -> bool:
        for alias in _aliases(item.value):
            escaped = re.escape(alias)
            compact = _normalize(raw_query)
            if re.search(rf"(?:除了{escaped}(?:之外|以外)?|不是{escaped}|非{escaped}|不(?:是|含){escaped})", compact):
                return True
            if re.search(rf"\b(?:not|except)\s+(?:the\s+)?{re.escape(alias)}\b", raw_query, re.I):
                return True
        return False

    @classmethod
    def _grouped_clauses(cls, raw_query: str, filters: list[CountFilter]) -> list[list[CountFilter]]:
        segments = [segment for segment in re.split(GROUP_SEPARATORS, raw_query, flags=re.IGNORECASE) if segment]
        if len(segments) < MIN_GROUP_SEGMENTS:
            return [[item] for item in filters]
        clauses: list[list[CountFilter]] = []
        for segment in segments:
            normalized_segment = _normalize(segment)
            clause = [
                item
                for item in filters
                if any(_alias_is_present(alias, segment, normalized_segment) for alias in _aliases(item.value))
            ]
            clause = list(dict.fromkeys(clause))
            if clause:
                clauses.append(clause)
        covered = {item for clause in clauses for item in clause}
        if len(covered) != len(set(filters)):
            return [[item] for item in filters]
        return clauses

    @staticmethod
    def _filters_from_query(query: str, objects: dict[str, dict[str, Any]]) -> list[CountFilter]:
        normalized_query = _normalize(query)
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
                if not any(_alias_is_present(alias, query, normalized_query) for alias in _aliases(value)):
                    continue
                key = (field_name, _normalize(value))
                if key not in seen:
                    found.append(CountFilter(field_name, value))
                    seen.add(key)
        return found
