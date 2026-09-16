from __future__ import annotations

import unittest

from arenaagent.competition.solvers.raven import RavenDecision


class RavenSolverTests(unittest.TestCase):
    def test_structured_output_records_confidence_and_margin(self) -> None:
        decision = RavenDecision.from_ranked([[1, 2, 3], [1, 2, 4]], [0.7, 0.2])
        self.assertIsNotNone(decision)
        self.assertEqual(decision.answer, [1, 2, 3])
        self.assertAlmostEqual(decision.confidence, 0.7)
        self.assertAlmostEqual(decision.margin, 0.5)
        self.assertFalse(decision.low_confidence)
        self.assertEqual(decision.context()["solver"], "local_resnet18_mlp")

    def test_missing_scores_are_explicitly_low_confidence(self) -> None:
        decision = RavenDecision.from_ranked([[8, 7, 6]])
        self.assertIsNotNone(decision)
        self.assertTrue(decision.low_confidence)
        self.assertEqual(decision.context()["answer"], [8, 7, 6])

    def test_empty_candidates_are_rejected(self) -> None:
        self.assertIsNone(RavenDecision.from_ranked([]))


if __name__ == "__main__":
    unittest.main()
