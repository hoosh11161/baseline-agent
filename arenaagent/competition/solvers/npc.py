from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def _normalize(value: Any) -> str:
    return re.sub(r"[\s，。！？,.!?;；:：]+", "", str(value or "")).lower()


def _normalize_question(value: Any) -> str:
    """Normalize harmless conversational wrappers without merging distinct questions."""
    text = _normalize(value)
    prefixes = ("麻烦请问", "麻烦告诉我", "请告诉我", "你知道", "请问", "please")
    suffixes = ("可以吗", "好吗", "吗", "呢")
    changed = True
    while changed and text:
        changed = False
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix) :]
                changed = True
                break
        for suffix in suffixes:
            if text.endswith(suffix):
                text = text[: -len(suffix)]
                changed = True
                break
    return text


@dataclass(slots=True)
class NPCMemory:
    allowed_people: set[str] = field(default_factory=set)
    known_facts: list[dict[str, Any]] = field(default_factory=list)
    asked_questions: set[tuple[str, str]] = field(default_factory=set)
    person_locations: dict[str, str] = field(default_factory=dict)
    object_locations: dict[str, str] = field(default_factory=dict)
    requirements: list[str] = field(default_factory=list)
    unresolved_questions: list[dict[str, str]] = field(default_factory=list)
    last_answer: str = ""

    def reset(self, subject: dict[str, Any]) -> None:
        mapping = subject.get("npc_asset_name")
        self.allowed_people = {str(name) for name in mapping} if isinstance(mapping, dict) else set()
        self.known_facts = []
        self.asked_questions = set()
        self.person_locations = {}
        self.object_locations = {}
        self.requirements = []
        self.unresolved_questions = []
        self.last_answer = ""

    def is_allowed(self, name: str) -> bool:
        return not self.allowed_people or str(name) in self.allowed_people

    def was_asked(self, name: str, question: str) -> bool:
        return (str(name), _normalize_question(question)) in self.asked_questions

    def record_exchange(self, name: str, question: str, reply: Any, hints: Any = None) -> None:
        target = str(name)
        normalized_question = _normalize_question(question)
        self.asked_questions.add((target, normalized_question))
        answer = str(reply or "").strip()
        self.last_answer = answer
        fact = {"npc": target, "question": str(question), "reply": answer, "hints": hints}
        if fact not in self.known_facts:
            self.known_facts.append(fact)
        if not answer:
            unresolved = {"npc": target, "question": str(question)}
            if unresolved not in self.unresolved_questions:
                self.unresolved_questions.append(unresolved)
            return
        self._parse_locations(answer)
        self._parse_requirements(answer)
        self.unresolved_questions = [
            item
            for item in self.unresolved_questions
            if not (item["npc"] == target and _normalize_question(item["question"]) == normalized_question)
        ]

    def ingest_fact(self, value: Any) -> None:
        if value in (None, "", {}, []):
            return
        text = str(value)
        self._parse_locations(text)
        self._parse_requirements(text)

    def _parse_locations(self, text: str) -> None:
        patterns = (
            r"([\u4e00-\u9fffA-Za-z0-9_]+?)\s*(?:在|位于)\s*([\u4e00-\u9fffA-Za-z0-9_]+)",
            r"([A-Za-z0-9_]+)\s+(?:is\s+)?(?:in|at|on)\s+([A-Za-z0-9_]+)",
        )
        for pattern in patterns:
            for raw_entity, raw_location in re.findall(pattern, text, flags=re.IGNORECASE):
                entity = raw_entity.strip()
                location = raw_location.strip()
                if not entity or not location:
                    continue
                if entity in self.allowed_people:
                    self.person_locations[entity] = location
                else:
                    self.object_locations[entity] = location

    def _parse_requirements(self, text: str) -> None:
        for match in re.findall(r"(?:需要|必须|require(?:s)?|need(?:s)?)\s*([^，。.!?]+)", text, flags=re.IGNORECASE):
            requirement = str(match).strip()
            if requirement and requirement not in self.requirements:
                self.requirements.append(requirement)

    def context(self) -> dict[str, Any]:
        return {
            "allowed_people": sorted(self.allowed_people),
            "known_facts": self.known_facts[-8:],
            "asked_questions": [list(item) for item in sorted(self.asked_questions)],
            "person_locations": dict(sorted(self.person_locations.items())),
            "object_locations": dict(sorted(self.object_locations.items())),
            "requirements": self.requirements[-8:],
            "unresolved_questions": self.unresolved_questions[-8:],
            "last_answer": self.last_answer,
        }
