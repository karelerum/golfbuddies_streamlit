import unittest

import pandas as pd

from aiapi.home_views import (
    build_home_chart_df,
    build_round_selector_options,
    format_numeric_value,
    get_home_round_options,
    prepare_course_chart_df,
    prepare_home_tournaments,
)


class HomeViewsTests(unittest.TestCase):
    def test_prepare_home_tournaments_filters_to_completed_tournaments_in_results(self):
        result_df = pd.DataFrame({"rundeid": ["20260101"]})
        tournament_df = pd.DataFrame(
            {
                "turneringsid": ["202601", "202501"],
                "turneringsnavn": ["VO 26", "VO 25"],
            }
        )
        round_info_df = pd.DataFrame(
            {
                "rundeid": ["20260101", "20250101"],
                "turneringsid": ["202601", "202501"],
                "ferdig_ind": [1, 0],
            }
        )

        filtered_tournaments, normalized_round_info = prepare_home_tournaments(result_df, tournament_df, round_info_df)

        self.assertEqual(filtered_tournaments["turneringsid"].tolist(), ["202601"])
        self.assertEqual(normalized_round_info["ferdig_ind"].tolist(), [1, 0])

    def test_get_home_round_options_builds_labels(self):
        round_info_df = pd.DataFrame(
            {
                "rundeid": ["20260101", "20260102"],
                "turneringsid": ["202601", "202601"],
                "runde": [1, 2],
                "bane": ["Meland", "Fana"],
                "ferdig_ind": [1, 1],
            }
        )
        result_df = pd.DataFrame({"rundeid": ["20260101", "20260102"]})

        round_options, label_map = get_home_round_options(round_info_df, result_df, "202601")

        self.assertEqual(round_options["runde"].astype(int).tolist(), [1, 2])
        self.assertEqual(label_map, {"1": "Meland (1)", "2": "Fana (2)"})

    def test_build_home_chart_df_groups_selected_tournament(self):
        result_df = pd.DataFrame(
            {
                "rundeid": ["20260101", "20260101", "20250101"],
                "spiller": ["Tore", "OleJ", "Tore"],
                "p6": [10, 8, 99],
            }
        )
        round_info_df = pd.DataFrame(
            {
                "rundeid": ["20260101", "20250101"],
                "turneringsid": ["202601", "202501"],
                "runde": [1, 1],
                "ferdig_ind": [1, 1],
            }
        )

        chart_df, value_column = build_home_chart_df(result_df, round_info_df, "202601", "P6", {"P6": "p6"})

        self.assertEqual(value_column, "p6")
        self.assertEqual(chart_df[["runde", "spiller", "p6"]].to_dict("records"), [{"runde": 1, "spiller": "OleJ", "p6": 8}, {"runde": 1, "spiller": "Tore", "p6": 10}])

    def test_build_round_selector_options_returns_labels_and_mapping(self):
        round_info_df = pd.DataFrame({"runde": [1, 2]})
        labels = {"1": "Meland (1)", "2": "Fana (2)"}

        values, option_labels, label_to_value = build_round_selector_options(round_info_df, labels)

        self.assertEqual(values, [1, 2])
        self.assertEqual(option_labels, ["Meland (1)", "Fana (2)"])
        self.assertEqual(label_to_value["Fana (2)"], 2)

    def test_prepare_course_chart_df_adds_stacking_columns(self):
        df = pd.DataFrame(
            {
                "spiller": pd.Categorical(["Tore", "Tore"], categories=["Tore"], ordered=True),
                "bane": ["Meland", "Fana"],
                "bane_order": [1, 2],
                "value": [10, 5],
                "total": [15, 15],
            }
        )

        prepared_df, bane_order, player_order, chart_title = prepare_course_chart_df(df, "P6")

        self.assertEqual(prepared_df["stacked_end"].tolist(), [10, 15])
        self.assertEqual(bane_order, ["Meland", "Fana"])
        self.assertEqual(player_order, ["Tore"])
        self.assertEqual(chart_title, "Poeng")

    def test_format_numeric_value_handles_empty_and_decimals(self):
        self.assertEqual(format_numeric_value(pd.NA), "")
        self.assertEqual(format_numeric_value(5.0), "5")
        self.assertEqual(format_numeric_value(5.25), "5.2")


if __name__ == "__main__":
    unittest.main()