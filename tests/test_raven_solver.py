from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from arenaagent.competition.solvers.raven import RavenDecision, RavenRuleVerifier


class RavenSolverTests(unittest.TestCase):
    def test_structured_output_records_confidence_and_margin(self) -> None:
        decision = RavenDecision.from_ranked([[1, 2, 3], [1, 2, 4]], [0.7, 0.2])
        self.assertIsNotNone(decision)
        self.assertEqual(decision.answer, [1, 2, 3])
        self.assertAlmostEqual(decision.confidence, 0.7)
        self.assertAlmostEqual(decision.margin, 0.5)
        self.assertFalse(decision.low_confidence)
        self.assertEqual(decision.context()["solver"], "local_resnet18_mlp_with_rule_verification")

    def test_missing_scores_are_explicitly_low_confidence(self) -> None:
        decision = RavenDecision.from_ranked([[8, 7, 6]])
        self.assertIsNotNone(decision)
        self.assertTrue(decision.low_confidence)
        self.assertEqual(decision.context()["answer"], [8, 7, 6])

    def test_empty_candidates_are_rejected(self) -> None:
        self.assertIsNone(RavenDecision.from_ranked([]))

    def test_union_rule_is_verified_and_ranks_matching_candidate(self) -> None:
        def panel(*boxes: tuple[int, int, int, int]) -> Image.Image:
            array = np.full((32, 32), 255, dtype=np.uint8)
            for left, top, right, bottom in boxes:
                array[top:bottom, left:right] = 0
            return Image.fromarray(array)

        left = (2, 10, 8, 22)
        right = (24, 10, 30, 22)
        top = (11, 2, 21, 8)
        bottom = (11, 24, 21, 30)
        diagonal_a = (3, 3, 9, 9)
        diagonal_b = (23, 23, 29, 29)
        problems = [
            panel(left),
            panel(right),
            panel(left, right),
            panel(top),
            panel(bottom),
            panel(top, bottom),
            panel(diagonal_a),
            panel(diagonal_b),
        ]
        answers = [
            panel(),
            panel(diagonal_a),
            panel(diagonal_b),
            panel(diagonal_a, diagonal_b),
            panel(left, right),
            panel(top, bottom),
            panel((0, 0, 32, 32)),
            panel((12, 12, 20, 20)),
        ]
        verification = RavenRuleVerifier().verify(problems, answers)
        self.assertIsNotNone(verification)
        self.assertEqual(int(np.argmax(verification.candidate_scores)), 3)
        self.assertTrue(any(item.rule == "union" for item in verification.hypotheses))
        self.assertGreater(verification.confidence, 0)


if __name__ == "__main__":
    unittest.main()
