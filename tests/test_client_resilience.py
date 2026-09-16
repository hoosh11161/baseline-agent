from __future__ import annotations

import unittest

from arenaagent.vlm_agent.client import Client


class AlwaysFailClient(Client):
    def _invoke(self, message):
        raise TimeoutError("provider timeout")


class ClientResilienceTests(unittest.TestCase):
    def test_exhausted_retries_return_error_not_fake_finish_action(self) -> None:
        response = AlwaysFailClient().invoke([], max_retries=1)
        self.assertEqual(response.text, "")
        self.assertIn("TimeoutError", response.error)
        self.assertNotIn("finish_task", response.text)


if __name__ == "__main__":
    unittest.main()
