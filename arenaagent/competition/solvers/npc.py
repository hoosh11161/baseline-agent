from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def _normalize(value: Any) -> str:
    return re.sub(r"[\s，。！？,.!?;；:：'\"的]+", "", str(value or "")).lower()


def _normalize_question(value: Any) -> str:
    """Normalize conversational wrappers and common semantic paraphrases."""
    text = _normalize(value)
    prefixes = ("麻烦请问", "麻烦告诉我", "请告诉我", "你知道", "能否告诉我", "请问", "please")
    suffixes = ("可以吗", "好吗", "吗", "呢", "please")
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
    replacements = {
        "在哪儿": "在哪里",
        "在什么地方": "在哪里",
        "位于何处": "在哪里",
        "位置是哪里": "在哪里",
        "是谁所有": "属于谁",
        "谁拥有": "属于谁",
        "是谁": "属于谁",
        "whereisthe": "whereis",
    }
    for source, target in replacements.items():
        text = text.replace(_normalize(source), _normalize(target))
    return text


def _entity_key(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^(?:这个|那个|一把|一个|一只|一件|the\s+)", "", text, flags=re.IGNORECASE)
    return _normalize(text)


def _task_text(subject: dict[str, Any]) -> str:
    return str(subject.get("subject") or subject.get("goal") or subject.get("task_prompt") or "")


@dataclass(slots=True, frozen=True)
class RequiredFact:
    kind: str
    entity: str

    @property
    def key(self) -> str:
        return f"{self.kind}:{_entity_key(self.entity)}"


@dataclass(slots=True, frozen=True)
class QuestionCandidate:
    npc: str
    question: str
    fact_key: str
    information_gain: float
    task_relevance: float
    already_known_penalty: float
    duplicate_penalty: float
    estimated_cost: float
    score: float
    reason: str

    def context(self) -> dict[str, Any]:
        return {
            "npc": self.npc,
            "question": self.question,
            "fact_key": self.fact_key,
            "information_gain": round(self.information_gain, 3),
            "task_relevance": round(self.task_relevance, 3),
            "already_known_penalty": round(self.already_known_penalty, 3),
            "duplicate_penalty": round(self.duplicate_penalty, 3),
            "estimated_cost": round(self.estimated_cost, 3),
            "score": round(self.score, 3),
            "reason": self.reason,
        }


@dataclass(slots=True)
class NPCMemory:
    allowed_people: set[str] = field(default_factory=set)
    task_text: str = ""
    required_facts: list[RequiredFact] = field(default_factory=list)
    known_facts: list[dict[str, Any]] = field(default_factory=list)
    asked_questions: set[tuple[str, str]] = field(default_factory=set)
    answered_questions: set[tuple[str, str]] = field(default_factory=set)
    person_locations: dict[str, str] = field(default_factory=dict)
    object_locations: dict[str, str] = field(default_factory=dict)
    ownership: dict[str, str] = field(default_factory=dict)
    requirement_by_entity: dict[str, str] = field(default_factory=dict)
    requirements: list[str] = field(default_factory=list)
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    unresolved_questions: list[dict[str, str]] = field(default_factory=list)
    last_answer: str = ""

    def reset(self, subject: dict[str, Any]) -> None:
        mapping = subject.get("npc_asset_name")
        self.allowed_people = {str(name) for name in mapping} if isinstance(mapping, dict) else set()
        self.task_text = _task_text(subject)
        self.required_facts = self.extract_required_facts(self.task_text)
        self.known_facts = []
        self.asked_questions = set()
        self.answered_questions = set()
        self.person_locations = {}
        self.object_locations = {}
        self.ownership = {}
        self.requirement_by_entity = {}
        self.requirements = []
        self.dependencies = {}
        self.unresolved_questions = []
        self.last_answer = ""

    @staticmethod
    def extract_required_facts(text: str) -> list[RequiredFact]:
        """Extract only high-confidence location/owner/requirement goals."""
        raw = str(text or "")
        facts: list[RequiredFact] = []
        location_patterns = (
            r"(?:找到|寻找|查找)\s*([\u4e00-\u9fffA-Za-z0-9_]{1,16}?)(?:并|，|,|然后|再|在哪里|的位置)",
            r"([\u4e00-\u9fffA-Za-z0-9_]{1,16}?)\s*(?:在哪里|在哪儿|在什么地方|位于何处|的位置(?:是哪里)?)",
            r"where\s+(?:is|are)\s+(?:the\s+)?([A-Za-z0-9_ -]{1,32}?)(?:\?|$|,)",
            r"(?:location|whereabouts)\s+of\s+(?:the\s+)?([A-Za-z0-9_ -]{1,32}?)(?:\?|$|,)",
        )
        owner_patterns = (
            r"谁(?:拥有|保管|拿着)\s*([\u4e00-\u9fffA-Za-z0-9_]{1,16})",
            r"([\u4e00-\u9fffA-Za-z0-9_]{1,16}?)\s*(?:是谁的|属于谁|由谁保管)",
            r"who\s+(?:owns|has|keeps)\s+(?:the\s+)?([A-Za-z0-9_ -]{1,32}?)(?:\?|$|,)",
        )
        requirement_patterns = (
            r"([\u4e00-\u9fffA-Za-z0-9_]{1,16}?)\s*(?:需要什么|需要哪些|的要求是什么)",
            r"what\s+does\s+([A-Za-z0-9_ -]{1,32}?)\s+need(?:\?|$|,)",
            r"requirements?\s+(?:for|of)\s+([A-Za-z0-9_ -]{1,32}?)(?:\?|$|,)",
        )
        for kind, patterns in (
            ("location", location_patterns),
            ("owner", owner_patterns),
            ("requirement", requirement_patterns),
        ):
            for pattern in patterns:
                for match in re.findall(pattern, raw, flags=re.IGNORECASE):
                    entity = NPCMemory._clean_extracted_entity(str(match))
                    fact = RequiredFact(kind, entity)
                    if entity and fact.key not in {item.key for item in facts}:
                        facts.append(fact)
        return facts

    @staticmethod
    def _clean_extracted_entity(value: str) -> str:
        value = re.sub(r"^(?:请|请问|告诉我|我想知道|你知道|找到|寻找|查找)", "", value.strip())
        value = re.split(r"(?:并告诉我|告诉我|然后|并且|and\s+tell)", value, maxsplit=1, flags=re.IGNORECASE)[0]
        if value in {"它", "他", "她", "it", "he", "she"}:
            return ""
        return value.strip(" ，,。.!?？")

    def is_allowed(self, name: str) -> bool:
        return not self.allowed_people or str(name) in self.allowed_people

    def was_asked(self, name: str, question: str) -> bool:
        return (str(name), _normalize_question(question)) in self.asked_questions

    def record_exchange(self, name: str, question: str, reply: Any, hints: Any = None) -> None:
        target = str(name)
        normalized_question = _normalize_question(question)
        question_key = (target, normalized_question)
        self.asked_questions.add(question_key)
        answer = str(reply or "").strip()
        self.last_answer = answer
        fact = {"npc": target, "question": str(question), "reply": answer, "hints": hints}
        if fact not in self.known_facts:
            self.known_facts.append(fact)
        if not answer:
            self._mark_unresolved(target, str(question))
            return
        before = {item.key for item in self.missing_facts()}
        self._parse_locations(answer)
        self._parse_ownership(answer)
        self._parse_requirements(answer)
        question_entities = [
            item.entity for item in self.required_facts if _entity_key(item.entity) in normalized_question
        ]
        self._parse_dependencies(answer, question_entities)
        after = {item.key for item in self.missing_facts()}
        if before - after or self._answer_is_redirect(answer):
            self.answered_questions.add(question_key)
            self.unresolved_questions = [
                item
                for item in self.unresolved_questions
                if not (item["npc"] == target and _normalize_question(item["question"]) == normalized_question)
            ]
        else:
            self._mark_unresolved(target, str(question))

    def ingest_fact(self, value: Any) -> None:
        if value in (None, "", {}, []):
            return
        text = str(value)
        self._parse_locations(text)
        self._parse_ownership(text)
        self._parse_requirements(text)
        self._parse_dependencies(text, [item.entity for item in self.required_facts])

    def _mark_unresolved(self, target: str, question: str) -> None:
        unresolved = {"npc": target, "question": question}
        if unresolved not in self.unresolved_questions:
            self.unresolved_questions.append(unresolved)

    def _parse_locations(self, text: str) -> None:
        patterns = (
            r"([\u4e00-\u9fffA-Za-z0-9_]+?)\s*(?:在|位于)\s*([\u4e00-\u9fffA-Za-z0-9_]+)",
            r"([A-Za-z0-9_]+)\s+(?:is\s+)?(?:in|at|on)\s+(?:the\s+)?([A-Za-z0-9_ -]+?)(?:[,.!?]|$)",
        )
        for pattern in patterns:
            for raw_entity, raw_location in re.findall(pattern, text, flags=re.IGNORECASE):
                entity = raw_entity.strip()
                location = raw_location.strip()
                if not entity or not location:
                    continue
                destination = self.person_locations if entity in self.allowed_people else self.object_locations
                destination[_entity_key(entity)] = location

    def _parse_ownership(self, text: str) -> None:
        pairs: list[tuple[str, str]] = []
        for item, owner in re.findall(
            r"([\u4e00-\u9fffA-Za-z0-9_]{1,16}?)\s*(?:是|属于)\s*([\u4e00-\u9fffA-Za-z0-9_]{1,16}?)(?:的|所有|保管)(?:[，。,.!?]|$)",
            text,
            flags=re.IGNORECASE,
        ):
            pairs.append((item, owner))
        for owner, item in re.findall(
            r"([\u4e00-\u9fffA-Za-z0-9_]{1,16}?)\s*(?:拥有|保管着|拿着)\s*([\u4e00-\u9fffA-Za-z0-9_]{1,16})",
            text,
            flags=re.IGNORECASE,
        ):
            pairs.append((item, owner))
        for item, owner in re.findall(
            r"(?:the\s+)?([A-Za-z0-9_ -]+?)\s+(?:belongs\s+to|is\s+owned\s+by)\s+([A-Za-z0-9_ -]+?)(?:[,.!?]|$)",
            text,
            flags=re.IGNORECASE,
        ):
            pairs.append((item, owner))
        for item, owner in pairs:
            if _entity_key(item) and str(owner).strip():
                self.ownership[_entity_key(item)] = str(owner).strip()

    def _parse_requirements(self, text: str) -> None:
        entity_patterns = (
            r"([\u4e00-\u9fffA-Za-z0-9_]{1,16}?)\s*(?:需要|必须)\s*([^，。.!?]+)",
            r"([A-Za-z0-9_ -]+?)\s+(?:requires?|needs?)\s+([^,.!?]+)",
        )
        for pattern in entity_patterns:
            for entity, raw_requirement in re.findall(pattern, text, flags=re.IGNORECASE):
                requirement = str(raw_requirement).strip()
                if not requirement:
                    continue
                self.requirement_by_entity[_entity_key(entity)] = requirement
                if requirement not in self.requirements:
                    self.requirements.append(requirement)

    def _parse_dependencies(self, text: str, entities: list[str]) -> None:
        targets: set[str] = set()
        for person in self.allowed_people:
            escaped = re.escape(person)
            if re.search(rf"(?:去|请|可以)?(?:问|询问|咨询)\s*{escaped}|(?:ask|consult)\s+{escaped}", text, re.I):
                targets.add(person)
        for entity in entities:
            owner = self.ownership.get(_entity_key(entity))
            if owner in self.allowed_people:
                targets.add(owner)
            if targets:
                self.dependencies.setdefault(_entity_key(entity), set()).update(targets)

    @staticmethod
    def _answer_is_redirect(answer: str) -> bool:
        return bool(re.search(r"(?:去|请|可以)?(?:问|询问|咨询)|(?:ask|consult)\s+", answer, re.I))

    def _known_value(self, fact: RequiredFact) -> str | None:
        key = _entity_key(fact.entity)
        if fact.kind == "location":
            return self.person_locations.get(key) or self.object_locations.get(key)
        if fact.kind == "owner":
            return self.ownership.get(key)
        if fact.kind == "requirement":
            return self.requirement_by_entity.get(key)
        return None

    def missing_facts(self) -> list[RequiredFact]:
        return [fact for fact in self.required_facts if not self._known_value(fact)]

    def is_complete(self) -> bool:
        return bool(self.required_facts) and not self.missing_facts()

    def final_answer(self) -> str | None:
        if not self.is_complete():
            return None
        values = [self._known_value(fact) for fact in self.required_facts]
        return "；".join(str(value) for value in values if value)

    def is_question_relevant(self, question: str) -> bool:
        if not self.required_facts:
            return True
        normalized = _normalize_question(question)
        kind_words = {
            "location": ("哪里", "位置", "where", "location"),
            "owner": ("谁", "拥有", "属于", "owner", "who"),
            "requirement": ("需要", "要求", "need", "require"),
        }
        for fact in self.missing_facts():
            mentions_entity = _entity_key(fact.entity) in normalized
            mentions_kind = any(_normalize(word) in normalized for word in kind_words[fact.kind])
            if mentions_entity and mentions_kind:
                return True
        return False

    def rank_questions(self) -> list[QuestionCandidate]:
        candidates: list[QuestionCandidate] = []
        for fact in self.missing_facts():
            preferred = set(self.dependencies.get(_entity_key(fact.entity), set()))
            owner = self.ownership.get(_entity_key(fact.entity))
            if owner in self.allowed_people:
                preferred.add(owner)
            for person in sorted(self.allowed_people):
                question = self._question_for(fact)
                duplicate = self.was_asked(person, question)
                information_gain = 1.25 if person in preferred else 1.0
                task_relevance = 1.0
                already_known_penalty = 2.0 if self._known_value(fact) else 0.0
                duplicate_penalty = 4.0 if duplicate else 0.0
                prior_cost = 0.15 * sum(target == person for target, _ in self.asked_questions)
                estimated_cost = 1.0 + prior_cost
                score = (
                    2.0 * information_gain
                    + task_relevance
                    - already_known_penalty
                    - duplicate_penalty
                    - 0.25 * estimated_cost
                )
                reason = "known owner/redirect" if person in preferred else "unasked allowed NPC"
                candidates.append(
                    QuestionCandidate(
                        npc=person,
                        question=question,
                        fact_key=fact.key,
                        information_gain=information_gain,
                        task_relevance=task_relevance,
                        already_known_penalty=already_known_penalty,
                        duplicate_penalty=duplicate_penalty,
                        estimated_cost=estimated_cost,
                        score=score,
                        reason=reason,
                    )
                )
        return sorted(candidates, key=lambda item: (-item.score, item.npc, item.fact_key))

    def best_question(self) -> QuestionCandidate | None:
        return next((item for item in self.rank_questions() if item.duplicate_penalty == 0), None)

    def _question_for(self, fact: RequiredFact) -> str:
        chinese = bool(re.search(r"[\u4e00-\u9fff]", self.task_text))
        if chinese:
            templates = {
                "location": f"{fact.entity}在哪里？",
                "owner": f"{fact.entity}属于谁？",
                "requirement": f"{fact.entity}需要什么？",
            }
        else:
            templates = {
                "location": f"Where is {fact.entity}?",
                "owner": f"Who owns {fact.entity}?",
                "requirement": f"What does {fact.entity} need?",
            }
        return templates[fact.kind]

    def context(self) -> dict[str, Any]:
        missing_keys = {item.key for item in self.missing_facts()}
        required_context = [
            {
                "kind": item.kind,
                "entity": item.entity,
                "key": item.key,
                "satisfied": item.key not in missing_keys,
                "value": self._known_value(item),
            }
            for item in self.required_facts
        ]
        ranked = self.rank_questions()[:5]
        return {
            "allowed_people": sorted(self.allowed_people),
            "required_facts": required_context,
            "known_facts": self.known_facts[-8:],
            "missing_facts": [item.key for item in self.missing_facts()],
            "asked_questions": [list(item) for item in sorted(self.asked_questions)],
            "answered_questions": [list(item) for item in sorted(self.answered_questions)],
            "person_locations": dict(sorted(self.person_locations.items())),
            "object_locations": dict(sorted(self.object_locations.items())),
            "ownership": dict(sorted(self.ownership.items())),
            "requirements": self.requirements[-8:],
            "dependencies": {key: sorted(value) for key, value in sorted(self.dependencies.items())},
            "unresolved_questions": self.unresolved_questions[-8:],
            "candidate_questions": [item.context() for item in ranked],
            "ready_to_answer": self.is_complete(),
            "last_answer": self.last_answer,
        }
