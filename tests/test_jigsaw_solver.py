from __future__ import annotations

import unittest

from arenaagent.competition.solvers.jigsaw import JigsawSpatialSolver


class JigsawSolverTests(unittest.TestCase):
    def test_infers_missing_cells_from_explicit_grid_dimensions(self) -> None:
        subject = {
            "reference_bounding": [0, 100, 100, 0],
            "rows": 2,
            "columns": 2,
            "piece_object_id": ["piece-a", "piece-b", "piece-c"],
        }
        objects = {"placed": {"position": [10, 25, 25]}}
        plan = JigsawSpatialSolver().infer(subject, objects)
        self.assertEqual(plan.y_centers, [25.0, 75.0])
        self.assertEqual(plan.z_centers, [25.0, 75.0])
        self.assertEqual(len(plan.missing_cells), 3)
        self.assertEqual(plan.pieces[0].candidate_position, [10.0, 75.0, 25.0])
        self.assertGreaterEqual(plan.confidence, 0.8)

    def test_no_case_specific_coordinates_without_public_bounds(self) -> None:
        plan = JigsawSpatialSolver().infer({}, {"piece": {"position": [1, 2, 3]}})
        self.assertEqual(plan.missing_cells, [])
        self.assertIn("unavailable", plan.reason)

    def test_observed_regular_grid_can_be_extended_without_hardcoded_case(self) -> None:
        subject = {"reference_bounding": [0, 100, 100, 0]}
        objects = {
            "a": {"position": [0, 25, 25]},
            "b": {"position": [0, 75, 25]},
            "c": {"position": [0, 25, 75]},
        }
        plan = JigsawSpatialSolver().infer(subject, objects)
        self.assertEqual(plan.y_centers, [25.0, 75.0])
        self.assertEqual(plan.z_centers, [25.0, 75.0])
        self.assertEqual(plan.missing_cells, [{"y": 75.0, "z": 75.0}])

    def test_grid_without_observed_x_plane_does_not_invent_coordinate(self) -> None:
        subject = {
            "reference_bounding": [0, 100, 100, 0],
            "rows": 2,
            "columns": 2,
            "piece_object_id": ["piece-a"],
        }
        plan = JigsawSpatialSolver().infer(subject, {})
        self.assertIsNone(plan.pieces[0].candidate_position)
        self.assertIn("no public X-plane evidence", plan.reason)

    def test_unplaced_piece_inside_bounds_does_not_occupy_a_grid_cell(self) -> None:
        subject = {
            "reference_bounding": [0, 100, 100, 0],
            "rows": 2,
            "columns": 2,
            "piece_object_id": ["piece-a"],
        }
        objects = {
            "piece-a": {"position": [99, 25, 25]},
            "placed": {"position": [10, 75, 75]},
        }
        plan = JigsawSpatialSolver().infer(subject, objects)
        self.assertEqual(len(plan.missing_cells), 3)
        self.assertIn({"y": 25.0, "z": 25.0}, plan.missing_cells)
        self.assertEqual(plan.pieces[0].current_position, [99.0, 25.0, 25.0])
        self.assertEqual(plan.pieces[0].candidate_position, [10.0, 25.0, 25.0])

    def test_failed_piece_retries_advance_through_finite_rotations(self) -> None:
        subject = {
            "reference_bounding": [0, 100, 100, 0],
            "rows": 2,
            "columns": 2,
            "piece_object_id": ["piece-a"],
        }
        objects = {"placed": {"position": [10, 25, 25]}}
        plan = JigsawSpatialSolver().infer(subject, objects, {"piece-a": 2})
        self.assertEqual(plan.pieces[0].rotation_attempt, 2)
        self.assertEqual(plan.pieces[0].candidate_rotation, {"roll": 0.0, "yaw": 180.0, "pitch": 0.0})
        wrapped = JigsawSpatialSolver().infer(subject, objects, {"piece-a": 4})
        self.assertEqual(wrapped.pieces[0].candidate_rotation["yaw"], 0.0)


if __name__ == "__main__":
    unittest.main()
