from __future__ import annotations

import unittest

from arenaagent.competition.runtime import CompetitionRuntime
from arenaagent.competition.solvers.npc import NPCMemory
from arenaagent.preliminary_baseline_agent.preliminary_baseline_agent import PreliminaryBaselineAgent


class NPCMemoryTests(unittest.TestCase):
    def test_parses_person_and_object_locations(self) -> None:
        memory = NPCMemory()
        memory.reset({"npc_asset_name": {"刘伟东": "npc_liu"}})
        memory.record_exchange("刘伟东", "他在哪里？", "刘伟东在厨房，钥匙在桌上。")
        self.assertEqual(memory.person_locations["刘伟东"], "厨房")
        self.assertEqual(memory.object_locations["钥匙"], "桌上")

    def test_duplicate_question_ignores_spacing_and_punctuation(self) -> None:
        memory = NPCMemory()
        memory.reset({"npc_asset_name": {"赵爷爷": "npc_zhao"}})
        memory.record_exchange("赵爷爷", "钥匙 在 哪里？", "钥匙在桌上")
        self.assertTrue(memory.was_asked("赵爷爷", "钥匙在哪里"))

    def test_duplicate_question_ignores_polite_wrappers(self) -> None:
        memory = NPCMemory()
        memory.reset({"npc_asset_name": {"赵爷爷": "npc_zhao"}})
        memory.record_exchange("赵爷爷", "请问钥匙在哪里？", "钥匙在桌上")
        self.assertTrue(memory.was_asked("赵爷爷", "你知道钥匙在哪里吗？"))

    def test_action_guard_rejects_unknown_npc(self) -> None:
        runtime = CompetitionRuntime()
        runtime.ensure_episode(
            {"task_type": "npc", "subject": "询问信息", "npc_asset_name": {"赵爷爷": "npc_zhao"}}
        )
        decision = runtime.validate_action(
            {
                "action": "speak_to_npc",
                "parameters": {"npc_name": "不存在的人", "message": "钥匙在哪里？"},
                "output": 0,
            }
        )
        self.assertFalse(decision.valid)
        self.assertEqual(decision.failure_class, "NPC_REASONING")

    def test_action_guard_accepts_allowed_npc_and_new_question(self) -> None:
        runtime = CompetitionRuntime()
        runtime.ensure_episode(
            {"task_type": "npc", "subject": "询问信息", "npc_asset_name": {"赵爷爷": "npc_zhao"}}
        )
        decision = runtime.validate_action(
            {
                "action": "speak_to_npc",
                "parameters": {"npc_name": "赵爷爷", "message": "钥匙在哪里？"},
                "output": 0,
            }
        )
        self.assertTrue(decision.valid)

    def test_agent_normalizes_known_pinyin_alias_before_guard(self) -> None:
        agent = PreliminaryBaselineAgent(stub=None, channel=None)
        agent._npc_name_to_asset_name = {"赵爷爷": "npc_zhao"}
        action = agent._normalize_action_parameters(
            {
                "action": "speak_to_npc",
                "parameters": {"npc_name": "zhaoyeye", "message": "钥匙在哪里？"},
                "output": 0,
            }
        )
        self.assertEqual(action["parameters"]["npc_name"], "赵爷爷")

    def test_agent_normalizes_official_asset_id_before_guard(self) -> None:
        agent = PreliminaryBaselineAgent(stub=None, channel=None)
        agent._npc_name_to_asset_name = {"赵爷爷": "npc_zhao"}
        action = agent._normalize_action_parameters(
            {
                "action": "move_to_npc",
                "parameters": {"npc_name": "npc_zhao"},
                "output": 0,
            }
        )
        self.assertEqual(action["parameters"]["npc_name"], "赵爷爷")

    def test_extracts_required_location_fact_and_tracks_missing_state(self) -> None:
        memory = NPCMemory()
        memory.reset(
            {
                "subject": "找到钥匙并告诉我它在哪里",
                "npc_asset_name": {"刘伟东": "npc_liu", "赵爷爷": "npc_zhao"},
            }
        )
        self.assertEqual([(item.kind, item.entity) for item in memory.required_facts], [("location", "钥匙")])
        self.assertEqual([item.key for item in memory.missing_facts()], ["location:钥匙"])
        self.assertFalse(memory.is_complete())

    def test_known_owner_ranks_owner_before_other_npcs(self) -> None:
        memory = NPCMemory()
        memory.reset(
            {
                "subject": "钥匙在哪里？",
                "npc_asset_name": {"刘伟东": "npc_liu", "赵爷爷": "npc_zhao"},
            }
        )
        memory.ingest_fact("钥匙是赵爷爷的。")
        ranked = memory.rank_questions()
        self.assertEqual(ranked[0].npc, "赵爷爷")
        self.assertEqual(ranked[0].fact_key, "location:钥匙")
        self.assertGreater(ranked[0].information_gain, ranked[1].information_gain)

    def test_multi_hop_redirect_updates_dependency_and_next_target(self) -> None:
        memory = NPCMemory()
        memory.reset(
            {
                "subject": "钥匙在哪里？",
                "npc_asset_name": {"刘伟东": "npc_liu", "赵爷爷": "npc_zhao"},
            }
        )
        memory.record_exchange("刘伟东", "钥匙在哪里？", "我不知道，请去问赵爷爷。")
        self.assertEqual(memory.dependencies["钥匙"], {"赵爷爷"})
        self.assertEqual(memory.best_question().npc, "赵爷爷")

    def test_semantic_duplicate_location_question_is_blocked(self) -> None:
        memory = NPCMemory()
        memory.reset({"subject": "钥匙在哪里？", "npc_asset_name": {"赵爷爷": "npc_zhao"}})
        memory.record_exchange("赵爷爷", "请问钥匙在哪儿？", "我不知道")
        self.assertTrue(memory.was_asked("赵爷爷", "钥匙在什么地方？"))
        self.assertIsNone(memory.best_question())

    def test_irrelevant_question_is_rejected_when_goal_is_known(self) -> None:
        runtime = CompetitionRuntime()
        runtime.ensure_episode(
            {"task_type": "npc", "subject": "钥匙在哪里？", "npc_asset_name": {"赵爷爷": "npc_zhao"}}
        )
        decision = runtime.validate_action(
            {
                "action": "speak_to_npc",
                "parameters": {"npc_name": "赵爷爷", "message": "今天天气怎么样？"},
                "output": 0,
            }
        )
        self.assertFalse(decision.valid)
        self.assertEqual(decision.failure_class, "NPC_BAD_QUESTION")

    def test_fact_answer_completes_goal_without_guessing(self) -> None:
        memory = NPCMemory()
        memory.reset({"subject": "钥匙在哪里？", "npc_asset_name": {"赵爷爷": "npc_zhao"}})
        memory.record_exchange("赵爷爷", "钥匙在哪里？", "钥匙在餐桌上。")
        self.assertTrue(memory.is_complete())
        self.assertEqual(memory.final_answer(), "餐桌上")


if __name__ == "__main__":
    unittest.main()
