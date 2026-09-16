from __future__ import annotations

import unittest

from arenaagent.vlm_agent.json_parsor import extract_last_json_from_text


class JsonParserTests(unittest.TestCase):
    def test_extracts_last_action_from_fenced_response(self) -> None:
        value = extract_last_json_from_text(
            'analysis first\n```json\n[{"action":"turn_in_degree","parameters":{"degree":45},"output":0}]\n```'
        )
        self.assertEqual(value[0]["action"], "turn_in_degree")

    def test_preserves_apostrophes_in_natural_language(self) -> None:
        value = extract_last_json_from_text(
            '[{"think":"don\'t guess", "action":"submit_answer", "parameters":{}, "output":"2"}]'
        )
        self.assertEqual(value[0]["think"], "don't guess")

    def test_handles_nested_arrays_and_braces_in_strings(self) -> None:
        value = extract_last_json_from_text(
            'prefix [{"think":"use {visible} facts", "action":"move_to_location", '
            '"parameters":{"target_location":[1,2,3]},"output":0}] suffix'
        )
        self.assertEqual(value[0]["parameters"]["target_location"], [1, 2, 3])

    def test_accepts_safe_python_literal_without_eval(self) -> None:
        value = extract_last_json_from_text(
            "[{'think': 'recover', 'action': 'turn_in_degree', 'parameters': {'degree': 45}, 'output': 0}]"
        )
        self.assertEqual(value[0]["parameters"]["degree"], 45)


if __name__ == "__main__":
    unittest.main()
