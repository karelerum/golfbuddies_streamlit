import unittest

import pandas as pd

from aiapi.player_views import build_player_round_history, filter_player_round_history, format_player_value_label


class PlayerViewsTests(unittest.TestCase):
    def test_build_player_round_history_groups_completed_rounds_for_player(self):
        result_df = pd.DataFrame(
            {
                "rundeid": ["20260102", "20260102", "20260102", "20260102", "20260101", "20260101", "20250101"],
                "spiller": ["Tore", "Tore", "OleJ", "OleJ", "Tore", "OleJ", "Tore"],
                "p6": [4, 5, 6, 5, 6, 2, 8],
                "slag": [3, 4, 4, 4, 5, 6, 7],
                "plass": [1, 1, 1, 1, 2, 3, 4],
                "par": [4, 4, 4, 4, 5, 5, 4],
            }
        )
        round_info_df = pd.DataFrame(
            {
                "rundeid": ["20260102", "20260101", "20250101"],
                "turneringsid": ["202601", "202601", "202501"],
                "runde": [2, 1, 1],
                "bane": ["Fana", "Meland", "Bergen"],
                "ferdig_ind": [1, 1, 0],
            }
        )
        tournament_df = pd.DataFrame(
            {
                "turneringsid": ["202601", "202501"],
                "turneringsnavn": ["VO 26", "VO 25"],
                "aar": [2026, 2025],
                "type": ["Sommer", "Vinter"],
            }
        )

        round_history_df = build_player_round_history(result_df, round_info_df, tournament_df, "Tore")

        self.assertEqual(round_history_df["rundeid"].tolist(), ["20260102", "20260101"])
        self.assertEqual(round_history_df["p6"].tolist(), [9, 6])
        self.assertEqual(round_history_df["slag"].tolist(), [7, 5])
        self.assertEqual(round_history_df["plass"].tolist(), [2, 1])
        self.assertEqual(round_history_df["par"].tolist(), [8, 5])
        self.assertEqual(round_history_df["mitt_par"].tolist(), [-1, 0])
        self.assertEqual(round_history_df["round_label"].tolist(), ["2026 - Fana", "2026 - Meland"])

    def test_filter_player_round_history_respects_tournament_type(self):
        round_history_df = pd.DataFrame(
            {
                "rundeid": ["20260101", "20250201"],
                "type": ["Sommer", "Vinter"],
                "round_label": ["20260101 - Meland", "20250201 - Simulator"],
            }
        )

        summer_df = filter_player_round_history(round_history_df, "Bare Sommer")
        winter_df = filter_player_round_history(round_history_df, "Bare Vinter")
        both_df = filter_player_round_history(round_history_df, "Begge")

        self.assertEqual(summer_df["rundeid"].tolist(), ["20260101"])
        self.assertEqual(winter_df["rundeid"].tolist(), ["20250201"])
        self.assertEqual(both_df["rundeid"].tolist(), ["20260101", "20250201"])

    def test_format_player_value_label_formats_each_value_type(self):
        self.assertEqual(format_player_value_label("P6", 9), "9 P")
        self.assertEqual(format_player_value_label("Slag", 71), "71 slag")
        self.assertEqual(format_player_value_label("Mitt par", 3), "+ 3")
        self.assertEqual(format_player_value_label("Mitt par", -2), "- 2")
        self.assertEqual(format_player_value_label("Plass", 1), "1")


if __name__ == "__main__":
    unittest.main()