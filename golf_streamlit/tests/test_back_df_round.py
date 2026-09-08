import unittest
from unittest.mock import patch

import pandas as pd

from aiapi.back_df_round import (
    _calculate_round_totals,
    _get_default_round_id,
    _get_round_options,
    _get_round_summary,
    _get_score_validation_messages,
    _get_visible_player_columns,
    _is_admin_player,
    _merge_edited_round_df,
    _prepare_round_df,
    _update_round_completion_status,
    format_round_to_simple_result,
)


class GetRoundOptionsTests(unittest.TestCase):
    @patch("aiapi.back_df_round.my_dfs.sqlite_enabled", return_value=False)
    def test_get_round_options_requires_initialized_sqlite(self, _sqlite_enabled):
        with self.assertRaisesRegex(ValueError, "SQLite er ikke initialisert"):
            _get_round_options()

    @patch("aiapi.back_df_round.my_dfs.sqlite_enabled", return_value=True)
    @patch("aiapi.back_df_round.my_dfs.get_table_list", return_value=pd.DataFrame())
    def test_get_round_options_requires_worksheet_list_data(self, _get_table_list, _sqlite_enabled):
        with self.assertRaisesRegex(ValueError, "Fant ingen data i worksheet_list"):
            _get_round_options()

    @patch("aiapi.back_df_round.my_dfs.sqlite_enabled", return_value=True)
    @patch(
        "aiapi.back_df_round.my_dfs.get_table_list",
        return_value=pd.DataFrame({"worksheet": ["20250101"]}),
    )
    def test_get_round_options_validates_required_columns(self, _get_table_list, _sqlite_enabled):
        with self.assertRaisesRegex(ValueError, "worksheet_list mangler kolonner: source"):
            _get_round_options()

    @patch("aiapi.back_df_round.my_dfs.sqlite_enabled", return_value=True)
    @patch(
        "aiapi.back_df_round.my_dfs.get_table_list",
        return_value=pd.DataFrame(
            {
                "source": ["Master", "Rounds", "Rounds"],
                "worksheet": ["rundeinfo", "20240101", "20240102"],
            }
        ),
    )
    def test_get_round_options_returns_sorted_rounds(self, _get_table_list, _sqlite_enabled):
        self.assertEqual(_get_round_options(), ["20240102", "20240101"])


class RoundSelectionTests(unittest.TestCase):
    @patch(
        "aiapi.back_df_round.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20260105", "20260104", "20260103"],
                "turneringsid": ["202601", "202601", "202601"],
                "runde": [5, 4, 3],
                "bane": ["A", "B", "C"],
                "ferdig_ind": [0, 0, 1],
                "paagaaende_ind": [0, 0, 0],
            }
        ),
    )
    def test_get_default_round_id_prefers_oldest_open_round(self, _get_round_info_df):
        self.assertEqual(_get_default_round_id(["20260105", "20260104", "20260103"]), "20260104")

    @patch(
        "aiapi.back_df_round.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20260105", "20260104", "20260103"],
                "turneringsid": ["202601", "202601", "202601"],
                "runde": [5, 4, 3],
                "bane": ["A", "B", "C"],
                "ferdig_ind": [1, 1, 1],
                "paagaaende_ind": [0, 0, 0],
            }
        ),
    )
    def test_get_default_round_id_falls_back_to_latest_finished_round(self, _get_round_info_df):
        self.assertEqual(_get_default_round_id(["20260105", "20260104", "20260103"]), "20260105")


class RoundSummaryTests(unittest.TestCase):
    @patch(
        "aiapi.back_df_round.my_dfs.get_tournament_info_df",
        return_value=pd.DataFrame({"turneringsid": ["202601"], "turneringsnavn": ["VO 26"]}),
    )
    @patch(
        "aiapi.back_df_round.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20260104"],
                "turneringsid": ["202601"],
                "runde": [4],
                "bane": ["Bjørnefjorden"],
                "ferdig_ind": [0],
                "paagaaende_ind": [1],
            }
        ),
    )
    def test_get_round_summary_includes_tournament_name_and_status(self, _get_round_info_df, _get_tournament_info_df):
        summary = _get_round_summary("20260104")

        self.assertEqual(summary["turneringsnavn"], "VO 26")
        self.assertEqual(summary["status"], "Pågår")
        self.assertEqual(summary["bane"], "Bjørnefjorden")


class PrepareRoundDfTests(unittest.TestCase):
    def test_prepare_round_df_requires_round_data(self):
        with self.assertRaisesRegex(ValueError, "Fant ingen data for valgt runde"):
            _prepare_round_df(pd.DataFrame())

    def test_prepare_round_df_requires_hull_column(self):
        with self.assertRaisesRegex(ValueError, "mangler kolonnen 'hull'"):
            _prepare_round_df(pd.DataFrame({"Tore": [4, 5]}))

    def test_prepare_round_df_rejects_invalid_hull_values(self):
        with self.assertRaisesRegex(ValueError, "Ugyldige hullverdier"):
            _prepare_round_df(pd.DataFrame({"hull": [1, "abc"], "Tore": [4, 5]}))

    def test_prepare_round_df_rejects_invalid_score_values(self):
        with self.assertRaisesRegex(ValueError, "Ugyldige slagverdier i kolonnen 'Tore'"):
            _prepare_round_df(pd.DataFrame({"hull": [1, 2], "Tore": [4, "x"]}))

    def test_prepare_round_df_allows_blank_score_values(self):
        prepared_df = _prepare_round_df(pd.DataFrame({"hull": [1, 2], "Tore": ["", "  "], "Doff": [None, 5]}))

        self.assertEqual(prepared_df["Tore"].tolist(), [pd.NA, pd.NA])
        self.assertEqual(prepared_df["Doff"].tolist(), [pd.NA, 5])

    def test_prepare_round_df_allows_stringified_na_values(self):
        prepared_df = _prepare_round_df(pd.DataFrame({"hull": [1, 2], "Tore": ["<NA>", "nan"], "Doff": ["None", 5]}))

        self.assertEqual(prepared_df["Tore"].tolist(), [pd.NA, pd.NA])
        self.assertEqual(prepared_df["Doff"].tolist(), [pd.NA, 5])

    def test_prepare_round_df_converts_numeric_columns(self):
        prepared_df = _prepare_round_df(pd.DataFrame({"hull": ["1", "2"], "Tore": [4, 5]}))

        self.assertEqual(str(prepared_df["hull"].dtype), "Int64")
        self.assertEqual(str(prepared_df["Tore"].dtype), "Int64")
        self.assertEqual(prepared_df["Tore"].tolist(), [4, 5])


class RoundDisplayTests(unittest.TestCase):
    def test_is_admin_player_uses_constants_list(self):
        self.assertTrue(_is_admin_player("Kåre"))
        self.assertFalse(_is_admin_player("Ole J"))
        self.assertFalse(_is_admin_player("Doff"))

    def test_get_visible_player_columns_returns_self_for_regular_player(self):
        round_df = pd.DataFrame({"hull": [1, 2], "Doff": [4, 5], "Tore": [3, 4]})
        self.assertEqual(_get_visible_player_columns(round_df, "Doff"), ["Doff"])

    def test_get_visible_player_columns_returns_all_for_admin_toggle(self):
        round_df = pd.DataFrame({"hull": [1, 2], "Doff": [4, 5], "Kåre": [3, 4]})
        self.assertEqual(_get_visible_player_columns(round_df, "Kåre", show_all_players=True), ["Doff", "Kåre"])

    def test_calculate_round_totals_handles_missing_values(self):
        round_df = pd.DataFrame({"hull": [1, 2], "Doff": [4, pd.NA], "Tore": [3, 5]})
        self.assertEqual(_calculate_round_totals(round_df, ["Doff", "Tore"]), {"Doff": 4, "Tore": 8})

    def test_merge_edited_round_df_preserves_hidden_player_columns(self):
        base_df = pd.DataFrame({"hull": [1, 2], "Doff": [4, 5], "Tore": [3, 4]})
        edited_df = pd.DataFrame({"hull": [1, 2], "Doff": [6, 7]})

        merged_df = _merge_edited_round_df(base_df, edited_df)

        self.assertEqual(merged_df.to_dict("records"), [{"hull": 1, "Doff": 6, "Tore": 3}, {"hull": 2, "Doff": 7, "Tore": 4}])

    def test_update_round_completion_status_updates_selected_round(self):
        round_info_df = pd.DataFrame(
            {
                "rundeid": ["20260103", "20260104"],
                "ferdig_ind": [1, 0],
                "paagaaende_ind": [0, 1],
            }
        )

        updated_df = _update_round_completion_status(round_info_df, "20260104", True)

        self.assertEqual(updated_df.loc[updated_df["rundeid"] == "20260104", "ferdig_ind"].iloc[0], 1)
        self.assertEqual(updated_df.loc[updated_df["rundeid"] == "20260104", "paagaaende_ind"].iloc[0], 0)

    @patch(
        "aiapi.back_df_round.my_dfs.get_hole_info_df",
        return_value=pd.DataFrame({"bane": ["Bergen", "Bergen"], "hull": [1, 2], "par": [4, 3]}),
    )
    @patch(
        "aiapi.back_df_round.my_dfs.get_tournament_info_df",
        return_value=pd.DataFrame({"turneringsid": ["202601"], "turneringsnavn": ["VO 26"]}),
    )
    @patch(
        "aiapi.back_df_round.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20260103"],
                "turneringsid": ["202601"],
                "runde": [3],
                "bane": ["Bergen"],
                "ferdig_ind": [1],
                "paagaaende_ind": [0],
            }
        ),
    )
    def test_get_score_validation_messages_returns_par_warnings(self, _get_round_info_df, _get_tournament_info_df, _get_hole_info_df):
        round_df = pd.DataFrame({"hull": [1, 2], "Doff": [11, 5]})

        warning_messages = _get_score_validation_messages(round_df, "20260103", ["Doff"])

        self.assertEqual(len(warning_messages), 1)
        self.assertIn("over maks 10", warning_messages[0])


class FormatRoundToSimpleResultTests(unittest.TestCase):
    def test_format_round_to_simple_result_skips_blank_scores(self):
        round_df = pd.DataFrame(
            {
                "hull": [1, 2],
                "Tore": [4, ""],
                "Doff": ["  ", 5],
            }
        )

        result_df = format_round_to_simple_result(round_df, "20260103")

        self.assertEqual(len(result_df), 2)
        self.assertEqual(
            result_df[["hull", "spiller", "slag"]].to_dict("records"),
            [
                {"hull": 1, "spiller": "Tore", "slag": 4},
                {"hull": 2, "spiller": "Doff", "slag": 5},
            ],
        )


if __name__ == "__main__":
    unittest.main()