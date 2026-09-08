import unittest

import pandas as pd

from aiapi.calc_result_columns import recalculate_6points, recalculate_placement, recalculate_slag_round_points


class Recalculate6PointsTests(unittest.TestCase):
    def test_recalculate_6points_sets_zero_when_slag_exceeds_par_plus_five(self):
        df = pd.DataFrame(
            {
                "rundeid": ["20260103", "20260103"],
                "hull": [1, 1],
                "spiller": ["Tore", "OleJ"],
                "slag": [4, 10],
                "par": [4, 4],
            }
        )

        df = recalculate_placement(df)
        result = recalculate_6points(df)

        self.assertEqual(result.loc[result["spiller"] == "Tore", "p6"].iloc[0], 6)
        self.assertEqual(result.loc[result["spiller"] == "OleJ", "p6"].iloc[0], 0)

    def test_two_way_tie_for_second_shares_points(self):
        df = pd.DataFrame(
            {
                "rundeid": ["20260103"] * 4,
                "hull": [1] * 4,
                "spiller": ["Kaare", "Trude", "Knut", "Elin"],
                "slag": [4, 5, 5, 6],
                "par": [4, 4, 4, 4],
            }
        )

        df = recalculate_placement(df)
        result = recalculate_6points(df).set_index("spiller")["p6"]

        self.assertEqual(result["Kaare"], 6)
        self.assertEqual(result["Trude"], 4.5)
        self.assertEqual(result["Knut"], 4.5)
        self.assertEqual(result["Elin"], 3)

    def test_three_way_tie_for_first_shares_points(self):
        df = pd.DataFrame(
            {
                "rundeid": ["20260103"] * 4,
                "hull": [1] * 4,
                "spiller": ["Kaare", "Trude", "Knut", "Elin"],
                "slag": [4, 4, 4, 6],
                "par": [4, 4, 4, 4],
            }
        )

        df = recalculate_placement(df)
        result = recalculate_6points(df).set_index("spiller")["p6"]

        self.assertEqual(result["Kaare"], 5.0)
        self.assertEqual(result["Trude"], 5.0)
        self.assertEqual(result["Knut"], 5.0)
        self.assertEqual(result["Elin"], 3)


class RecalculateSlagRoundPointsTests(unittest.TestCase):
    def test_points_are_written_to_p6_from_total_round_placement(self):
        players = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"]
        totals = {player: index + 10 for index, player in enumerate(players)}
        df = pd.DataFrame(
            [
                {"rundeid": "R1", "hull": hole, "spiller": player, "slag": totals[player]}
                for hole in [1, 2]
                for player in players
            ]
        )

        result = recalculate_slag_round_points(df)

        self.assertEqual(
            result.drop_duplicates("spiller").sort_values("spiller")["p6"].tolist(),
            [18, 15, 12, 9, 6, 3, 0, 0],
        )

    def test_tied_total_strokes_share_points_and_skip_next_place(self):
        df = pd.DataFrame(
            {
                "rundeid": ["R1"] * 4,
                "hull": [1] * 4,
                "spiller": ["A", "B", "C", "D"],
                "slag": [70, 70, 71, 72],
            }
        )

        result = recalculate_slag_round_points(df)

        self.assertEqual(result.set_index("spiller")["p6"].to_dict(), {"A": 18, "B": 18, "C": 12, "D": 9})


if __name__ == "__main__":
    unittest.main()