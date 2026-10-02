import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
from route_sensitivity import (
    center_weights, route, router, sparse_matrix, summarize_routes, vector_stats,
)


class SensitivityTests(unittest.TestCase):
    def test_sparse_matrix_keeps_row_mass_and_stable_tie_order(self):
        matrix = {"q": {"green": 0.7, "water": 0.7, "rest": 0.9, "culture": 0.1}}
        sparse = sparse_matrix(matrix, 2)["q"]
        self.assertEqual([s for s, v in sparse.items() if v], ["green", "rest"])
        self.assertAlmostEqual(sum(sparse.values()), 2.4)
        self.assertAlmostEqual(sparse["rest"] / sparse["green"], 0.9 / 0.7)
        self.assertEqual(matrix["q"]["water"], 0.7)

    def test_centering_uses_actual_rounded_mean(self):
        weights = {"a": 0.3333, "b": 0.3333, "c": 0.3333}
        self.assertTrue(all(abs(v) < 1e-15 for v in center_weights(weights).values()))
        centered = center_weights({"a": 0.2, "b": 0.8})
        self.assertAlmostEqual(centered["a"], -0.3)
        self.assertAlmostEqual(sum(centered.values()), 0.0)

    def test_standard_deviation_is_population_not_sample(self):
        stats = vector_stats([{"a": 0}, {"a": 0}, {"a": 1}])["a"]
        self.assertEqual((stats["min"], stats["max"]), (0, 1))
        self.assertAlmostEqual(stats["std_population"], math.sqrt(2 / 9))

    def test_mean_detour_weights_days_not_unique_paths(self):
        def item(key, length):
            return {"route_id": key, "length_m": length, "min_edge_cost_factor": 1,
                    "negative_luck_segment_count": 0}
        result = summarize_routes([item("a", 10), item("a", 10), item("b", 14)], 10)
        self.assertEqual(result["unique_route_count"], 2)
        self.assertEqual(result["day_to_day_changes"], 1)
        self.assertAlmostEqual(result["mean_detour_m"], 4 / 3)

    def test_amplification_can_trade_distance_for_quality(self):
        def edge(i, a, b, length, green):
            return {"id": i, "coords": [a, b], "length": length,
                    "qualities": {**dict.fromkeys(router.QUALITIES, 0.0), "green": green}}
        # Direct path: length 10, quality 0.2; detour: length 14, quality 0.5.
        segments = [edge(0, [0, 0], [1, 1], 10, 0.2),
                    edge(1, [0, 0], [1, 0], 7, 0.5),
                    edge(2, [1, 0], [1, 1], 7, 0.5)]
        baseline = route(segments, (0, 0), (1, 1), {"green": 1}, alpha=1)
        amplified = route(segments, (0, 0), (1, 1), {"green": 1}, alpha=2)
        self.assertEqual(baseline["segment_ids"], [0])
        self.assertEqual(amplified["segment_ids"], [1, 2])
        self.assertAlmostEqual(amplified["length_m"] - baseline["length_m"], 4)

    def test_nonpositive_cost_is_rejected_before_search(self):
        segments = [{"id": 0, "coords": [[0, 0], [1, 1]], "length": 1,
                     "qualities": dict.fromkeys(router.QUALITIES, 1.0)}]
        with self.assertRaisesRegex(ValueError, "nonpositive"):
            route(segments, (0, 0), (1, 1), {"green": 1}, alpha=2)


if __name__ == "__main__":
    unittest.main()
