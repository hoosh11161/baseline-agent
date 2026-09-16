from __future__ import annotations

import unittest

from arenaagent.competition.solvers.counting import CountingSolver


class CountingSolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.objects = {
            "1": {"object_id": "1", "name": "cup", "color": "Red", "shape": "Cylinder"},
            "2": {"object_id": "2", "name": "cup", "color": "Blue", "shape": "Cylinder"},
            "3": {"object_id": "3", "name": "ball", "color": "Red", "shape": "Sphere"},
        }

    def test_attribute_filter_is_deterministic(self) -> None:
        result = CountingSolver().solve("有多少红色物体", self.objects)
        self.assertTrue(result.confident)
        self.assertEqual(result.answer, 2)
        self.assertEqual(result.matched_ids, ["1", "3"])

    def test_two_classes_are_counted_separately_without_guessing_format(self) -> None:
        result = CountingSolver().solve("分别有多少红色和蓝色物体", self.objects)
        self.assertFalse(result.confident)
        self.assertIsNone(result.answer)
        self.assertEqual(result.grouped_counts, {"color=Blue": 1, "color=Red": 2})

    def test_same_field_alternatives_are_counted_as_union_for_one_total(self) -> None:
        result = CountingSolver().solve("红色或蓝色物体总共有多少", self.objects)
        self.assertTrue(result.confident)
        self.assertEqual(result.answer, 3)
        self.assertEqual(result.matched_ids, ["1", "2", "3"])

    def test_alternatives_with_another_attribute_use_or_then_and(self) -> None:
        result = CountingSolver().solve("红色或蓝色球体总共有多少", self.objects)
        self.assertTrue(result.confident)
        self.assertEqual(result.answer, 1)
        self.assertEqual(result.matched_ids, ["3"])

    def test_multiple_attributes_are_combined(self) -> None:
        result = CountingSolver().solve("有多少红色球体", self.objects)
        self.assertTrue(result.confident)
        self.assertEqual(result.answer, 1)
        self.assertEqual(result.matched_ids, ["3"])

    def test_empty_scene_returns_zero(self) -> None:
        result = CountingSolver().solve("有多少物体", {})
        self.assertTrue(result.confident)
        self.assertEqual(result.answer, 0)

    def test_scan_is_bounded(self) -> None:
        solver = CountingSolver([90, 180])
        solver.observe("episode")
        self.assertEqual(solver.next_scan_action()["parameters"]["degree"], 90)
        self.assertEqual(solver.next_scan_action()["parameters"]["degree"], 180)
        self.assertIsNone(solver.next_scan_action())
        self.assertTrue(solver.coverage_complete)


if __name__ == "__main__":
    unittest.main()
