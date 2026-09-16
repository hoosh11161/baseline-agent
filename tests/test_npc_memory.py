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


if __name__ == "__main__":
    unittest.main()
