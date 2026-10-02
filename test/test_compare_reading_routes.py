import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from compare_reading_routes import decompose, find_route, overlap, router


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.matrix = {
            "activation": {"green": 1.0, "water": 0.0},
            "flow": {"green": 0.0, "water": 1.0},
        }
        self.saju = {"activation": 0.2, "flow": 0.0}
        self.astrology = {"activation": 0.0, "flow": 0.6}

    def test_equal_input_coefficients_do_not_imply_equal_output_shares(self):
        result = decompose(self.saju, self.astrology,
                           {"activation": 0.1, "flow": 0.3}, self.matrix,
                           {"green": 0.25, "water": 0.75})
        self.assertAlmostEqual(result["ideal_saju_share"], 0.25)
        self.assertAlmostEqual(result["ideal_astrology_share"], 0.75)
        self.assertAlmostEqual(result["attributes"]["green"]["ideal_saju"], 0.25)
        self.assertAlmostEqual(result["attributes"]["green"]["ideal_astrology"], 0.0)

    def test_rounding_residual_is_not_assigned_to_either_system(self):
        result = decompose(self.saju, self.astrology,
                           {"activation": 0.11, "flow": 0.3}, self.matrix,
                           {"green": 0.2683, "water": 0.7317})
        self.assertAlmostEqual(result["production_saju_share"], 0.1 / 0.41)
        self.assertAlmostEqual(result["production_astrology_share"], 0.3 / 0.41)
        self.assertAlmostEqual(result["intermediate_rounding_residual_total"], 0.01 / 0.41)
        for row in result["attributes"].values():
            self.assertAlmostEqual(row["production_saju"] + row["production_astrology"]
                                   + row["intermediate_rounding_residual"]
                                   + row["final_rounding_residual"], row["routed_combined"])

    def test_zero_mass_is_rejected(self):
        zero = {"activation": 0.0, "flow": 0.0}
        with self.assertRaises(ValueError):
            decompose(zero, zero, zero, self.matrix, {"green": 0.0, "water": 0.0})


class OverlapTests(unittest.TestCase):
    def test_overlap_uses_lengths_and_both_denominators(self):
        segments = [{"length": 10}, {"length": 90}, {"length": 190}]
        result = overlap([0, 1], [0, 2], segments)
        self.assertEqual(result["shared_length_m"], 10)
        self.assertEqual(result["union_length_m"], 290)
        self.assertAlmostEqual(result["length_jaccard"], 10 / 290)
        self.assertAlmostEqual(result["fraction_of_left"], 0.1)
        self.assertAlmostEqual(result["fraction_of_right"], 0.05)

    def test_identical_and_disjoint_routes(self):
        segments = [{"length": 10}, {"length": 90}]
        self.assertEqual(overlap([0, 1], [1, 0], segments)["length_jaccard"], 1)
        self.assertEqual(overlap([0], [1], segments)["length_jaccard"], 0)


class RoutingTests(unittest.TestCase):
    def test_changed_weights_can_select_different_routes(self):
        segments = [
            {"id": 0, "coords": [[0, 0], [1, 0]], "length": 1,
             "qualities": {"green": 1, "water": 0}},
            {"id": 1, "coords": [[1, 0], [1, 1]], "length": 1,
             "qualities": {"green": 1, "water": 0}},
            {"id": 2, "coords": [[0, 0], [0, 1]], "length": 1,
             "qualities": {"green": 0, "water": 1}},
            {"id": 3, "coords": [[0, 1], [1, 1]], "length": 1,
             "qualities": {"green": 0, "water": 1}},
        ]
        for segment in segments:
            segment["qualities"] = {
                **dict.fromkeys(router.QUALITIES, 0.0), **segment["qualities"]
            }
        _, green = find_route(segments, {"green": 1, "water": 0}, [0, 0], [1, 1])
        _, water = find_route(segments, {"green": 0, "water": 1}, [0, 0], [1, 1])
        self.assertEqual(green, [0, 1])
        self.assertEqual(water, [2, 3])


if __name__ == "__main__":
    unittest.main()
