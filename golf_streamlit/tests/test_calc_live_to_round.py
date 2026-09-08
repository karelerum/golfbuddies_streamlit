import unittest

import pandas as pd

from aiapi.calc_live_to_round import calculate_live_round_df


class CalcLiveToRoundTests(unittest.TestCase):
    def test_floors_and_distributes_to_largest_fraction(self):
        source_df = pd.DataFrame({"hull": [1, 2, 3]})
        score_dfs = [
            pd.DataFrame({"hull": [1, 2, 3], "Tore": [4, 3, 4]}),
            pd.DataFrame({"hull": [1, 2, 3], "Tore": [5, 3, 5]}),
        ]

        result_df = calculate_live_round_df(source_df, score_dfs, ["Tore"])

        # Averages are 4.5, 3, 4.5. One remainder stroke goes to hole 1.
        self.assertEqual(result_df["Tore"].tolist(), [5, 3, 4])
        self.assertEqual(int(result_df["Tore"].sum()), 12)

    def test_corrects_rounding_that_would_reverse_exact_ranking(self):
        source_df = pd.DataFrame({"hull": [1, 2]})
        score_dfs = [
            pd.DataFrame({"hull": [1, 2], "Bedre": [4, 4], "Verre": [4, 4]}),
            pd.DataFrame({"hull": [1, 2], "Bedre": [4, 4], "Verre": [4, 4]}),
            pd.DataFrame({"hull": [1, 2], "Bedre": [5, 4], "Verre": [4, 4]}),
            pd.DataFrame({"hull": [1, 2], "Bedre": [5, 4], "Verre": [5, 4]}),
            pd.DataFrame({"hull": [1, 2], "Bedre": [5, 4], "Verre": [5, 4]}),
        ]

        result_df = calculate_live_round_df(source_df, score_dfs, ["Bedre", "Verre"])

        # Exact totals: Verre 8.4, Bedre 8.6. Lower exact total remains better.
        self.assertLessEqual(result_df["Verre"].sum(), result_df["Bedre"].sum())

    def test_missing_scores_remain_empty(self):
        source_df = pd.DataFrame({"hull": [1, 2]})
        score_dfs = [pd.DataFrame({"hull": [1, 2], "Tore": [4, pd.NA]})]

        result_df = calculate_live_round_df(source_df, score_dfs, ["Tore"])

        self.assertEqual(result_df["Tore"].tolist(), [4, pd.NA])


if __name__ == "__main__":
    unittest.main()
