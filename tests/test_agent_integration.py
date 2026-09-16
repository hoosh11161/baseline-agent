from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arenaagent.preliminary_baseline_agent.preliminary_baseline_agent import (
    PreliminaryBaselineAgent,
    PreliminaryBaselineAgentCfg,
)
from arenaagent.vlm_agent.client import ClientResponse
from arenaagent.vlm_agent.prompt import PromptGenerator


class FakeTongSim:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def acquire_first_person_perception(self, character_id, width=None, height=None):
        return {"image": None, "objects": [{"object_id": "1", "name": "cup", "color": "Red"}]}

    def has_object_in_hand(self, character_id):
        return False, None

    def move_and_take_object(self, character_id, object_id, **kwargs):
        self.calls.append(("move_and_take_object", object_id))
        return {"result": "success"}

    def turn_in_degree(self, character_id, degree):
        self.calls.append(("turn_in_degree", degree))
        return {"result": "success"}


class FakeClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return ClientResponse(
            text=self.text,
            token_usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )


class RaisingClient:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        raise TimeoutError("model timeout")


class RaisingTongSim(FakeTongSim):
    def acquire_first_person_perception(self, character_id, width=None, height=None):
        raise ConnectionError("perception unavailable")


class AgentIntegrationTests(unittest.TestCase):
    def make_agent(self, response_text: str) -> tuple[PreliminaryBaselineAgent, FakeTongSim, FakeClient]:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        cfg = PreliminaryBaselineAgentCfg(log_dir=self.temp_dir.name)
        agent = PreliminaryBaselineAgent(stub=None, channel=None, cfg=cfg)
        tongsim = FakeTongSim()
        client = FakeClient(response_text)
        agent._initialized = True
        agent.tongsim = tongsim
        agent.character_id = "character-1"
        agent.vlm_client = client
        agent.prompt_generator = PromptGenerator(agent.cfg.vlm_config.prompt_config)
        agent.action_space = {"key": "answer"}
        return agent, tongsim, client

    def test_hallucinated_id_never_reaches_tongsim(self) -> None:
        agent, tongsim, client = self.make_agent(
            '[{"think":"guess","action":"move_and_take_object",'
            '"parameters":{"object_id":"999"},"output":0}]'
        )
        result = agent.run_step({"task_type": "tidyroom", "subject": "整理房间"}, {})
        self.assertEqual(client.calls, 1)
        self.assertEqual(tongsim.calls, [])
        self.assertTrue(result["locally_blocked"])
        self.assertEqual(agent._competition.metrics.invalid_actions, 1)

    def test_prompt_renders_action_schema_and_world_state(self) -> None:
        agent, _, _ = self.make_agent("not used")
        agent._competition.ensure_episode({"task_type": "counting", "subject": "计数"})
        agent._competition.observe([{"object_id": "1", "color": "Red"}])
        variables = agent._build_prompt_variables(
            {"task_type": "counting", "subject": "计数"},
            {},
            {"submit_answer": {"sig": "(output:any)"}},
            [{"object_id": "1", "color": "Red"}],
            False,
        )
        messages = agent.prompt_generator.Generate(variables=variables)
        self.assertIn("submit_answer", messages[0]["content"])
        self.assertNotIn("{self.api_info}", messages[0]["content"])
        user_text = messages[-1]["content"][1]["text"]
        self.assertIn("unique_objects_seen", user_text)
        self.assertNotIn("{self.competition_state}", user_text)

    def test_visible_id_reaches_tongsim(self) -> None:
        agent, tongsim, _ = self.make_agent(
            '[{"think":"visible","action":"move_and_take_object",'
            '"parameters":{"object_id":"1"},"output":0}]'
        )
        result = agent.run_step({"task_type": "tidyroom", "subject": "整理房间"}, {})
        self.assertEqual(result["result"], "success")
        self.assertEqual(tongsim.calls, [("move_and_take_object", "1")])

    def test_raven_routes_to_local_solver_without_llm_call(self) -> None:
        agent, _, client = self.make_agent("not used")
        with patch("arenaagent.vlm_agent.vlm_agent.handle_raven_skill", return_value={"answer": [1, 2, 3]}):
            result = agent.run_step({"task_type": "raven", "subject": "瑞文", "task_data": {}}, {})
        self.assertEqual(client.calls, 0)
        self.assertEqual(result, {"answer": [1, 2, 3]})

    def test_official_evaluation_writes_verified_episode(self) -> None:
        agent, _, _ = self.make_agent(
            '[{"think":"visible","action":"move_and_take_object",'
            '"parameters":{"object_id":"1"},"output":0}]'
        )
        agent.run_step({"task_id": "verified-1", "task_type": "tidyroom", "subject": "整理房间"}, {})
        agent._on_subject_evaluated({"success": True, "score": 1})
        path = Path(self.temp_dir.name) / "metrics" / "episode_verified-1.json"
        self.assertTrue(path.exists())
        payload = path.read_text(encoding="utf-8")
        self.assertIn('"verified": true', payload)
        self.assertIn('"prompt_fingerprint"', payload)
        self.assertNotIn('"api_key"', payload)

    def test_model_timeout_is_recoverable_and_does_not_call_tongsim(self) -> None:
        agent, tongsim, _ = self.make_agent("not used")
        client = RaisingClient()
        agent.vlm_client = client
        result = agent.run_step({"task_id": "timeout-1", "task_type": "tidyroom", "subject": "整理房间"}, {})
        self.assertEqual(client.calls, 1)
        self.assertEqual(tongsim.calls, [])
        self.assertTrue(result["recoverable"])
        self.assertEqual(result["failure_class"], "MODEL_ERROR")
        self.assertEqual(agent._competition.metrics.model_errors, 1)
        self.assertEqual(agent._competition.metrics.steps, 1)

    def test_perception_failure_is_recoverable(self) -> None:
        agent, _, client = self.make_agent("not used")
        agent.tongsim = RaisingTongSim()
        result = agent.run_step({"task_id": "vision-1", "task_type": "counting", "subject": "计数"}, {})
        self.assertEqual(client.calls, 0)
        self.assertTrue(result["recoverable"])
        self.assertEqual(result["failure_class"], "PERCEPTION_ERROR")
        self.assertEqual(agent._competition.metrics.perception_errors, 1)
        self.assertEqual(agent._competition.metrics.vision_calls, 1)
        self.assertEqual(agent._competition.first_failure["step"], 1)

    def test_counting_uses_bounded_scan_then_deterministic_submit(self) -> None:
        agent, tongsim, client = self.make_agent("model must not be called")
        subject = {"task_id": "count-1", "task_type": "counting", "subject": "有多少红色物体"}
        for _ in range(3):
            result = agent.run_step(subject, {})
            self.assertEqual(result["result"], "success")
        result = agent.run_step(subject, {})
        self.assertEqual(result, {"answer": "1"})
        self.assertEqual(client.calls, 0)
        self.assertEqual(
            tongsim.calls,
            [("turn_in_degree", 90.0), ("turn_in_degree", 180.0), ("turn_in_degree", 270.0)],
        )


if __name__ == "__main__":
    unittest.main()
