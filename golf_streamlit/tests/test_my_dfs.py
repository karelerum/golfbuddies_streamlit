import unittest
from unittest.mock import patch

import pandas as pd

from aiapi.sqlite import SQLiteOperationError
from src import my_dfs


class ResultatBaneStackedTests(unittest.TestCase):
    @patch("src.my_dfs.get_sqlite_df_with_query", side_effect=SQLiteOperationError("boom"))
    def test_get_round_df_raises_contextual_sqlite_error(self, _get_sqlite_df_with_query):
        with self.assertRaises(SQLiteOperationError):
            my_dfs.get_round_df("20250101")

    @patch(
        "src.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20250101", "20250102", "20250103"],
                "turneringsid": ["202501", "202501", "202501"],
                "runde": [1, 2, 3],
                "bane": ["Meland", "Fana", "Bergen"],
                "ferdig_ind": [1, 1, 1],
            }
        ),
    )
    @patch(
        "src.my_dfs.get_result_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20250101", "20250101", "20250102", "20250102", "20250103", "20250103"],
                "spiller": ["Tore", "OleJ", "Tore", "OleJ", "Tore", "OleJ"],
                "p6": [82, 68.5, 86, 74.5, 87, 72],
                "slag": [70, 74, 71, 73, 69, 72],
            }
        ),
    )
    def test_resultat_bane_stacked_groups_by_player_and_course(self, _get_result_df, _get_round_info_df):
        df = my_dfs.resultat_bane_stacked("202501", "P6")

        self.assertEqual(df["spiller"].cat.categories.tolist(), ["Tore", "OleJ"])
        self.assertEqual(df["bane"].tolist(), ["Meland", "Fana", "Bergen", "Meland", "Fana", "Bergen"])
        self.assertEqual(df["value"].tolist(), [82, 86, 87, 68.5, 74.5, 72])
        self.assertEqual(df["total"].tolist(), [255, 255, 255, 215, 215, 215])

    @patch(
        "src.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20250101", "20250102"],
                "turneringsid": ["202501", "202501"],
                "runde": [1, 2],
                "bane": ["Meland", "Fana"],
                "ferdig_ind": [1, 1],
            }
        ),
    )
    @patch(
        "src.my_dfs.get_result_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20250101", "20250101", "20250102", "20250102"],
                "spiller": ["Tore", "OleJ", "Tore", "OleJ"],
                "p6": [82, 68.5, 86, 74.5],
                "slag": [75, 69, 73, 70],
            }
        ),
    )
    def test_resultat_bane_stacked_sorts_strokes_lowest_total_first(self, _get_result_df, _get_round_info_df):
        df = my_dfs.resultat_bane_stacked("202501", "Slag")

        self.assertEqual(df["spiller"].cat.categories.tolist(), ["OleJ", "Tore"])

    @patch(
        "src.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20250101", "20250102"],
                "turneringsid": ["202501", "202501"],
                "runde": [1, 2],
                "bane": ["Meland", "Fana"],
                "ferdig_ind": [1, 1],
            }
        ),
    )
    @patch(
        "src.my_dfs.get_result_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20250101", "20250101", "20250101", "20250101", "20250102", "20250102"],
                "hull": [1, 1, 2, 2, 1, 1],
                "spiller": ["Tore", "OleJ", "Tore", "OleJ", "Tore", "OleJ"],
                "slag": [4, 3, 5, 4, 3, 5],
                "par": [4, 4, 4, 4, 4, 4],
            }
        ),
    )
    def test_resultat_goy_gruppen_runde_calculates_best_score_per_hole_from_slag(self, _get_result_df, _get_round_info_df):
        df = my_dfs.resultat_goy_gruppen_runde("202501")

        self.assertEqual(
            df.to_dict("records"),
            [{"Runde": 1, "Bane": "Meland", "Gruppens par": "- 1"}, {"Runde": 2, "Bane": "Fana", "Gruppens par": "- 1"}],
        )


if __name__ == "__main__":
    unittest.main()