import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

import pandas as pd

from aiapi.live_round import (
    LIVE_ROUNDS_TABLE,
    LiveRoundError,
    _build_completed_live_round_df,
    _set_slag_runde_ind,
    advance_to_next_live_round,
    confirm_live_hole,
    create_live_round,
    delete_live_round,
    finalize_live_round_session,
    get_live_overview,
    get_live_round_candidates,
    get_live_round_details,
    reset_live_round,
    save_live_hole_scores,
    update_live_round_setup,
)
from ui.pages.live_runde_data import _build_all_scores_rows, _build_overview_rows
from ui.pages.live_runde_views import _all_scores_registered, _is_registration_submit_event


class LiveRoundTests(unittest.TestCase):
    def test_all_scores_registered_requires_a_score_for_every_player(self):
        self.assertFalse(_all_scores_registered(["Tore", "Kari"], {"Tore": 4}))
        self.assertFalse(_all_scores_registered([], {}))
        self.assertTrue(_all_scores_registered(["Tore", "Kari"], {"Tore": 4, "Kari": 5}))

    def test_registration_submit_requires_new_user_click_for_current_hole(self):
        valid_event = {"user_clicked": True, "event_id": "event-1", "hole": 2, "scores": {"Tore": 5}}

        self.assertTrue(_is_registration_submit_event(valid_event, 2, None))
        self.assertFalse(_is_registration_submit_event(valid_event, 3, None))
        self.assertFalse(_is_registration_submit_event(valid_event, 2, "event-1"))
        self.assertFalse(_is_registration_submit_event({**valid_event, "user_clicked": False}, 2, None))
        self.assertFalse(_is_registration_submit_event({"hole": 2, "scores": {"Tore": 5}}, 2, None))

    @patch("aiapi.live_round.clear_cached_df")
    @patch("aiapi.live_round.update_sqlite_row")
    @patch("aiapi.live_round.get_sqlite_df")
    @patch("aiapi.live_round._fresh_session_in_transaction")
    @patch("aiapi.live_round.db.transaction")
    @patch("aiapi.live_round._get_par_by_hull", return_value={1: 4})
    @patch("aiapi.live_round.get_live_round_access")
    def test_save_live_hole_scores_updates_only_active_group_columns(
        self,
        mock_get_access,
        _mock_par_by_hull,
        mock_transaction,
        mock_fresh_session,
        mock_get_sqlite_df,
        mock_update_sqlite_row,
        mock_clear_cached_df,
    ):
        round_setup = {"runde": 1, "score_table": "live_score_123", "gruppe_klar": {"1": [], "2": []}}
        session = {"bane": "Fana", "rundeoppsett": [round_setup]}
        score_df = pd.DataFrame({"hull": [1], "Tore": [pd.NA], "Kari": [pd.NA], "Ola": [5]})
        mock_get_access.return_value = {"session": session, "gruppe": 1, "spillere": ["Tore", "Kari"]}
        mock_transaction.return_value = nullcontext(Mock())
        mock_fresh_session.return_value = (session, pd.DataFrame())
        mock_get_sqlite_df.return_value = score_df

        save_live_hole_scores("live_123", "Tore", 1, {"Tore": 4, "Kari": 3})

        score_update = mock_update_sqlite_row.call_args_list[0]
        self.assertEqual(score_update.args[1:4], ("live_score_123", "hull", 1))
        self.assertEqual(score_update.args[4], {"Tore": 4, "Kari": 3})
        self.assertNotIn("Ola", score_update.args[4])
        self.assertEqual(mock_update_sqlite_row.call_args_list[1].args[1], LIVE_ROUNDS_TABLE)
        mock_clear_cached_df.assert_any_call("live_score_123")

    @patch("aiapi.live_round.my_dfs.save_table_df", return_value=True)
    @patch("aiapi.live_round._get_par_by_hull", return_value={1: 4})
    @patch("aiapi.live_round._get_round_score_df")
    @patch("aiapi.live_round.get_live_round_access")
    def test_save_live_hole_scores_rejects_incomplete_group_before_writing(
        self,
        mock_get_access,
        mock_get_score_df,
        _mock_par_by_hull,
        mock_save_table_df,
    ):
        mock_get_access.return_value = {
            "session": {"rundeoppsett": [{"runde": 1, "score_table": "live_score_123"}]},
            "gruppe": 1,
            "spillere": ["Tore", "Kari"],
        }
        mock_get_score_df.return_value = pd.DataFrame({"hull": [1], "Tore": [pd.NA], "Kari": [pd.NA]})

        with self.assertRaisesRegex(LiveRoundError, "Alle spillere"):
            save_live_hole_scores("live_123", "Tore", 1, {"Tore": 4})

        mock_save_table_df.assert_not_called()

    @patch("aiapi.live_round._get_round_score_df")
    @patch(
        "aiapi.live_round.my_dfs.get_round_df",
        return_value=pd.DataFrame({"hull": [1, 2]}),
    )
    def test_completed_live_round_averages_and_rounds_scores(self, _get_round_df, mock_get_score_df):
        mock_get_score_df.side_effect = [
            pd.DataFrame({"hull": [1, 2], "Tore": [4, 3]}),
            pd.DataFrame({"hull": [1, 2], "Tore": [5, 3]}),
            pd.DataFrame({"hull": [1, 2], "Tore": [4, 3]}),
            pd.DataFrame({"hull": [1, 2], "Tore": [5, 4]}),
            pd.DataFrame({"hull": [1, 2], "Tore": [4, 3]}),
            pd.DataFrame({"hull": [1, 2], "Tore": [5, 4]}),
        ]
        session = {
            "source_rundeid": "20260105",
            "spillere": [{"spiller": "Tore"}],
            "rundeoppsett": [{"runde": 1}, {"runde": 2}, {"runde": 3}, {"runde": 4}, {"runde": 5}, {"runde": 6}],
        }

        completed_df = _build_completed_live_round_df(session)

        self.assertEqual(completed_df["Tore"].tolist(), [5, 3])

    @patch("aiapi.live_round.table_exists", return_value=False)
    @patch(
        "aiapi.live_round.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20260101", "20260102"],
                "turneringsid": ["202601", "202601"],
                "runde": [1, 2],
                "bane": ["Fana", "Meland"],
                "ferdig_ind": [0, 1],
                "paagaaende_ind": [0, 1],
            }
        ),
    )
    def test_candidates_only_include_unfinished_rounds(self, _get_round_info_df, _table_exists):
        candidates_df = get_live_round_candidates()

        self.assertEqual(candidates_df["rundeid"].tolist(), ["20260101"])

    @patch("aiapi.live_round.my_dfs.save_round_info_df", return_value=True)
    @patch("aiapi.live_round.get_cached_df", return_value=None)
    @patch("aiapi.live_round.set_cached_df")
    @patch("aiapi.live_round.my_dfs.save_table_df", return_value=True)
    @patch(
        "aiapi.live_round.my_dfs.get_round_df",
        return_value=pd.DataFrame({"hull": [1, 2], "Tore": [pd.NA, pd.NA]}),
    )
    @patch("aiapi.live_round.table_exists", return_value=False)
    @patch(
        "aiapi.live_round.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20260101"],
                "turneringsid": ["202601"],
                "runde": [1],
                "bane": ["Fana"],
                "ferdig_ind": [0],
            }
        ),
    )
    def test_create_live_round_copies_scorecard_and_metadata(
        self,
        _get_round_info_df,
        _table_exists,
        _get_round_df,
        save_table_df,
        set_cached_df,
        _get_cached_df,
        _save_round_info_df,
    ):
        live_rundeid = create_live_round(
            "20260101",
            "Fredagsrunde",
            ["Tore", "Kari"],
            ["Ola"],
            {"Tore": -2, "Kari": 0, "Ola": 3},
            antall_runder=2,
        )

        self.assertEqual(live_rundeid, "live_runde_20260101_runde_1")
        self.assertEqual(save_table_df.call_args_list[0].args[0], "live_runde_20260101_runde_1")
        self.assertEqual(save_table_df.call_args_list[1].args[0], LIVE_ROUNDS_TABLE)
        self.assertEqual(save_table_df.call_args_list[0].args[1].columns.tolist(), ["hull", "Tore", "Kari", "Ola"])
        self.assertEqual(save_table_df.call_args_list[1].args[1].loc[0, "antall_runder"], 2)
        self.assertEqual(set_cached_df.call_count, 2)

    @patch("aiapi.live_round.table_exists", return_value=False)
    @patch(
        "aiapi.live_round.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "rundeid": ["20260101"],
                "turneringsid": ["202601"],
                "runde": [1],
                "bane": ["Fana"],
                "ferdig_ind": [1],
            }
        ),
    )
    def test_create_live_round_rejects_completed_round(self, _get_round_info_df, _table_exists):
        with self.assertRaisesRegex(LiveRoundError, "ikke tilgjengelig"):
            create_live_round("20260101", "Test", ["Tore"], [])

    def test_create_live_round_rejects_invalid_player_setup(self):
        with self.assertRaisesRegex(LiveRoundError, "Tittel"):
            create_live_round("20260101", "", ["Tore"], [])
        with self.assertRaisesRegex(LiveRoundError, "én gruppe"):
            create_live_round("20260101", "Test", ["Tore"], ["Tore"])
        with self.assertRaisesRegex(LiveRoundError, "maksimalt fire"):
            create_live_round("20260101", "Test", ["A", "B", "C", "D", "E"], [])
        with self.assertRaisesRegex(LiveRoundError, "Antall runder"):
            create_live_round("20260101", "Test", ["Tore"], [], antall_runder=4)

    @patch("aiapi.live_round.my_dfs.save_round_info_df", return_value=True)
    @patch("aiapi.live_round.my_dfs.get_round_info_df", return_value=pd.DataFrame({"rundeid": ["20260101"], "slag_runde_ind": [1]}))
    @patch("aiapi.live_round._save_live_rounds_df")
    @patch("aiapi.live_round._get_live_rounds_df")
    def test_delete_live_round_removes_matching_row(
        self, mock_get_live_rounds_df, mock_save_live_rounds_df, _get_round_info_df, _save_round_info_df
    ):
        mock_get_live_rounds_df.return_value = pd.DataFrame(
            {"live_rundeid": ["live_123", "live_456"], "source_rundeid": ["20260101", "20260102"]}
        )

        delete_live_round("live_123")

        saved_df = mock_save_live_rounds_df.call_args.args[0]
        self.assertEqual(saved_df["live_rundeid"].tolist(), ["live_456"])

    @patch("aiapi.gsheet_sync.sync_df_to_gsheet")
    @patch("aiapi.live_round.my_dfs.save_round_info_df", return_value=True)
    @patch(
        "aiapi.live_round.my_dfs.get_round_info_df",
        return_value=pd.DataFrame({"rundeid": ["20260101"], "slag_runde_ind": [0]}),
    )
    def test_live_round_flag_is_local_only(self, _get_round_info_df, save_round_info_df, sync_df_to_gsheet):
        _set_slag_runde_ind("20260101", 1)

        self.assertEqual(save_round_info_df.call_args.args[0].loc[0, "slag_runde_ind"], 1)
        sync_df_to_gsheet.assert_not_called()

    @patch("aiapi.live_round._save_completed_live_round")
    @patch("aiapi.live_round._set_slag_runde_ind")
    @patch("aiapi.live_round._set_finalization_status")
    @patch("aiapi.live_round.clear_cached_df")
    @patch("aiapi.live_round.update_sqlite_row")
    @patch("aiapi.live_round._fresh_session_in_transaction")
    @patch("aiapi.live_round.db.transaction")
    @patch("aiapi.live_round.get_live_round_access")
    def test_finalize_live_round_syncs_once_after_all_rounds_complete(
        self,
        mock_get_access,
        mock_transaction,
        mock_fresh_session,
        _mock_update_row,
        _mock_clear_cache,
        mock_set_status,
        mock_set_flag,
        mock_save_completed,
    ):
        session = {
            "source_rundeid": "20260101",
            "type_runde": "Slag",
            "rundeoppsett": [{"runde": 1, "score_table": "live_score_123", "fullfort": True}],
        }
        mock_get_access.return_value = {"session": session}
        mock_transaction.return_value = nullcontext(Mock())
        mock_fresh_session.return_value = (session, pd.DataFrame())
        mock_save_completed.return_value = Mock(sync_report=Mock(ok=True))

        finalize_live_round_session("live_123", "Tore")

        mock_set_flag.assert_called_once_with("20260101", 0)
        mock_save_completed.assert_called_once_with(session)
        mock_set_status.assert_called_once_with("live_123", session, "completed")

    @patch("aiapi.live_round._save_completed_live_round")
    @patch("aiapi.live_round._set_finalization_status")
    @patch("aiapi.live_round.clear_cached_df")
    @patch("aiapi.live_round.update_sqlite_row")
    @patch("aiapi.live_round._fresh_session_in_transaction")
    @patch("aiapi.live_round.db.transaction")
    @patch("aiapi.live_round.get_live_round_access")
    def test_finalize_live_round_marks_failed_sync_for_retry(
        self,
        mock_get_access,
        mock_transaction,
        mock_fresh_session,
        _mock_update_row,
        _mock_clear_cache,
        mock_set_status,
        mock_save_completed,
    ):
        session = {
            "source_rundeid": "20260101",
            "type_runde": "Slag",
            "rundeoppsett": [{"runde": 1, "score_table": "live_score_123", "fullfort": True}],
        }
        mock_get_access.return_value = {"session": session}
        mock_transaction.return_value = nullcontext(Mock())
        mock_fresh_session.return_value = (session, pd.DataFrame())
        mock_save_completed.return_value = Mock(sync_report=Mock(ok=False))

        with self.assertRaisesRegex(LiveRoundError, "ikke fullført"):
            finalize_live_round_session("live_123", "Tore")

        mock_set_status.assert_called_once_with("live_123", session, "failed")

    @patch("aiapi.live_round._save_completed_live_round")
    @patch("aiapi.live_round._fresh_session_in_transaction")
    @patch("aiapi.live_round.db.transaction")
    @patch("aiapi.live_round.get_live_round_access")
    def test_finalize_live_round_is_noop_when_already_completed(
        self,
        mock_get_access,
        mock_transaction,
        mock_fresh_session,
        mock_save_completed,
    ):
        session = {
            "rundeoppsett": [
                {
                    "runde": 1,
                    "score_table": "live_score_123",
                    "fullfort": True,
                    "finalization_status": "completed",
                }
            ]
        }
        mock_get_access.return_value = {"session": session}
        mock_transaction.return_value = nullcontext(Mock())
        mock_fresh_session.return_value = (session, pd.DataFrame())

        finalize_live_round_session("live_123", "Tore")

        mock_save_completed.assert_not_called()

    def test_delete_live_round_rejects_unknown_id(self):
        with patch("aiapi.live_round._get_live_rounds_df", return_value=pd.DataFrame({"live_rundeid": ["live_456"]})):
            with self.assertRaisesRegex(LiveRoundError, "Fant ikke"):
                delete_live_round("live_123")

    @patch("aiapi.live_round._save_live_rounds_df")
    @patch("aiapi.live_round._get_live_rounds_df")
    @patch("aiapi.live_round.my_dfs.save_table_df", return_value=True)
    @patch("aiapi.live_round._get_round_score_df", return_value=pd.DataFrame({"hull": [1, 2], "Tore": [pd.NA, pd.NA]}))
    @patch("aiapi.live_round.get_live_round_details")
    def test_update_live_round_setup_allows_player_change_without_scores(
        self, mock_get_details, _mock_score_df, mock_save_table_df, mock_get_live_rounds_df, _mock_save_live_rounds_df
    ):
        mock_get_details.return_value = {
            "live_rundeid": "live_123",
            "tittel": "Gammel tittel",
            "spillere": [{"spiller": "Tore", "gruppe": 1, "startverdi": 0}],
            "rundeoppsett": [{"runde": 1, "score_table": "live_score_123", "startverdier": {"Tore": 0}}],
        }
        mock_get_live_rounds_df.return_value = pd.DataFrame({"live_rundeid": ["live_123"], "tittel": ["Gammel tittel"]})

        update_live_round_setup("live_123", "Ny tittel", ["Tore", "Kari"], [], antall_runder=2)

        saved_score_df = mock_save_table_df.call_args.args[1]
        self.assertEqual(saved_score_df.columns.tolist(), ["hull", "Tore", "Kari"])

    @patch("aiapi.live_round._get_round_score_df", return_value=pd.DataFrame({"hull": [1, 2], "Tore": [3, pd.NA]}))
    @patch("aiapi.live_round.get_live_round_details")
    def test_update_live_round_setup_rejects_player_change_after_scores(self, mock_get_details, _mock_score_df):
        mock_get_details.return_value = {
            "live_rundeid": "live_123",
            "tittel": "Gammel tittel",
            "spillere": [{"spiller": "Tore", "gruppe": 1, "startverdi": 0}],
            "rundeoppsett": [{"runde": 1, "score_table": "live_score_123", "startverdier": {"Tore": 0}}],
        }

        with self.assertRaisesRegex(LiveRoundError, "Kan ikke endre spillerne"):
            update_live_round_setup("live_123", "Ny tittel", ["Tore", "Kari"], [])

    @patch(
        "aiapi.live_round.get_active_live_rounds",
        return_value=pd.DataFrame(
            {
                "live_rundeid": ["live_runde_20260101"],
                "tittel": ["Fredagsrunde"],
                "spillere": ['[{"spiller": "Tore", "gruppe": 1, "startverdi": -2}]'],
            }
        ),
    )
    def test_live_round_details_decodes_player_setup(self, _get_active_live_rounds):
        details = get_live_round_details("live_runde_20260101")

        self.assertEqual(details["tittel"], "Fredagsrunde")
        self.assertEqual(details["spillere"], [{"spiller": "Tore", "gruppe": 1, "startverdi": -2}])

    @patch("aiapi.live_round._get_par_by_hull", return_value={1: 3, 2: 4})
    @patch("aiapi.live_round._get_round_score_df", return_value=pd.DataFrame({"hull": [1, 2], "Tore": [3, 4], "Ola": [4, 5]}))
    @patch("aiapi.live_round._get_round_setup", return_value={"startverdier": {"Tore": 0, "Ola": 0}, "gruppe_klar": {"1": [], "2": []}})
    @patch(
        "aiapi.live_round.get_live_round_access",
        return_value={
            "spillere": ["Tore"],
            "session": {"spillere": [{"spiller": "Tore", "gruppe": 1}, {"spiller": "Ola", "gruppe": 2}]},
        },
    )
    def test_overview_hides_unpublished_opponent_scores(
        self,
        _get_access,
        _get_round_setup,
        _get_score_df,
        _get_par_by_hull,
    ):
        overview_df = get_live_overview("live_runde_20260101", "Tore")

        self.assertEqual(overview_df["spiller"].tolist(), ["Tore"])
        self.assertEqual(overview_df.loc[0, "rundens_slag"], 7)

    def test_build_overview_rows_formats_json_safe_values(self):
        overview_df = pd.DataFrame(
            {
                "plassering": [1, 2],
                "spiller": ["Tore", "Kari"],
                "spillers_par": [-1, 2],
                "rundens_slag": [34, 37],
            }
        )

        rows = _build_overview_rows(overview_df)

        self.assertEqual(
            rows,
            [
                {"plassering": 1, "spiller": "Tore", "spillers_par": -1, "rundens_slag": 34},
                {"plassering": 2, "spiller": "Kari", "spillers_par": 2, "rundens_slag": 37},
            ],
        )

    def test_build_all_scores_rows_includes_par_limits_and_empty_scores(self):
        score_df = pd.DataFrame(
            {
                "hull": [2, 1],
                "Tore": [pd.NA, 3],
                "Kari": [5, pd.NA],
            }
        )

        rows = _build_all_scores_rows(score_df, ["Tore", "Kari"], {1: 3, 2: 4})

        self.assertEqual(
            rows,
            [
                {"hull": 1, "par": 3, "max_score": 9, "scores": {"Tore": 3, "Kari": None}},
                {"hull": 2, "par": 4, "max_score": 10, "scores": {"Tore": None, "Kari": 5}},
            ],
        )

    def test_build_all_scores_rows_masks_unpublished_opposing_scores(self):
        score_df = pd.DataFrame(
            {
                "hull": [1, 2],
                "Tore": [3, 4],
                "Ola": [4, 5],
            }
        )

        # Tore is in own group (G1), Ola is in opposing group (G2). Only Hull 1 is published.
        rows = _build_all_scores_rows(
            score_df,
            ["Tore", "Ola"],
            {1: 3, 2: 4},
            own_group_players={"Tore"},
            published_hulls={1},
        )

        self.assertEqual(
            rows,
            [
                {"hull": 1, "par": 3, "max_score": 9, "scores": {"Tore": 3, "Ola": 4}},
                {"hull": 2, "par": 4, "max_score": 10, "scores": {"Tore": 4, "Ola": None}},
            ],
        )

    @patch("aiapi.live_round._save_live_rounds_df")
    @patch("aiapi.live_round._get_live_rounds_df")
    @patch("aiapi.live_round.set_cached_df")
    @patch("aiapi.live_round.my_dfs.save_table_df", return_value=True)
    @patch("aiapi.live_round.get_sqlite_df")
    @patch("aiapi.live_round.table_exists", return_value=True)
    @patch("aiapi.live_round.get_live_round_details")
    def test_reset_live_round_clears_scores_and_published_hulls(
        self,
        mock_get_details,
        _mock_table_exists,
        mock_get_sqlite_df,
        mock_save_table_df,
        _mock_set_cached_df,
        mock_get_live_rounds_df,
        mock_save_live_rounds_df,
    ):
        mock_get_details.return_value = {
            "live_rundeid": "live_123",
            "spillere": [{"spiller": "Tore", "gruppe": 1}, {"spiller": "Ola", "gruppe": 2}],
            "rundeoppsett": [
                {
                    "runde": 1,
                    "score_table": "live_score_123",
                    "gruppe_klar": {"1": [1], "2": [1]},
                    "fullfort": True,
                }
            ],
        }
        mock_get_sqlite_df.return_value = pd.DataFrame({"hull": [1, 2], "Tore": [3, 4], "Ola": [4, 5]})
        mock_get_live_rounds_df.return_value = pd.DataFrame({"live_rundeid": ["live_123"], "rundeoppsett": ["[]"]})

        reset_live_round("live_123")

        saved_score_df = mock_save_table_df.call_args_list[0].args[1]
        self.assertTrue(saved_score_df["Tore"].isna().all())
        self.assertTrue(saved_score_df["Ola"].isna().all())
        mock_save_live_rounds_df.assert_called_once()

    @patch("aiapi.live_round.clear_cached_df")
    @patch("aiapi.live_round.update_sqlite_row")
    @patch("aiapi.live_round.get_sqlite_df")
    @patch("aiapi.live_round._fresh_session_in_transaction")
    @patch("aiapi.live_round.db.transaction")
    @patch("aiapi.live_round.get_live_round_access")
    def test_confirm_live_hole_requires_both_groups_before_marking_fullfort(
        self,
        mock_get_access,
        mock_transaction,
        mock_fresh_session,
        mock_get_sqlite_df,
        _mock_update_sqlite_row,
        _mock_clear_cached_df,
    ):
        round_setup = {
            "runde": 1,
            "score_table": "live_score_123",
            "gruppe_klar": {"1": [], "2": [1]},
            "fullfort": False,
        }
        session = {"rundeoppsett": [round_setup]}
        mock_transaction.return_value = nullcontext(Mock())
        mock_fresh_session.side_effect = lambda _conn, _live_id, _fallback: (session, pd.DataFrame())
        mock_get_access.return_value = {"session": session, "gruppe": 1, "spillere": ["Tore"]}
        mock_get_sqlite_df.return_value = pd.DataFrame({"hull": [1, 2], "Tore": [3, 4], "Ola": [4, 5]})

        is_published_after_group1 = confirm_live_hole("live_123", "Tore", 2)

        # Kun gruppe 1 har bekreftet hull 2 (siste hull) - runden skal IKKE være fullført.
        self.assertFalse(is_published_after_group1)
        self.assertFalse(round_setup["fullfort"])

        mock_get_access.return_value = {"session": session, "gruppe": 2, "spillere": ["Ola"]}
        is_published_after_group2 = confirm_live_hole("live_123", "Ola", 2)

        # Begge grupper har nå bekreftet siste hull - runden er fullført.
        self.assertTrue(is_published_after_group2)
        self.assertTrue(round_setup["fullfort"])

    @patch("aiapi.live_round.set_cached_df")
    @patch("aiapi.live_round._save_live_rounds_df")
    @patch("aiapi.live_round._get_live_rounds_df")
    @patch("aiapi.live_round.my_dfs.save_table_df", return_value=True)
    @patch("aiapi.live_round.my_dfs.get_round_df", return_value=pd.DataFrame({"hull": [1, 2]}))
    @patch("aiapi.live_round._get_par_by_hull", return_value={1: 3, 2: 4})
    @patch("aiapi.live_round._get_round_score_df", return_value=pd.DataFrame({"hull": [1, 2], "Tore": [3, 4], "Ola": [4, 5]}))
    @patch("aiapi.live_round.get_live_round_access")
    def test_advance_to_next_live_round_carries_over_standings(
        self,
        mock_get_access,
        _mock_score_df,
        _mock_par_by_hull,
        _mock_get_round_df,
        mock_save_table_df,
        mock_get_live_rounds_df,
        _mock_save_live_rounds_df,
        _mock_set_cached_df,
    ):
        round_setup = {
            "runde": 1,
            "score_table": "live_score_1",
            "startverdier": {"Tore": 0, "Ola": 0},
            "gruppe_klar": {"1": [], "2": []},
            "fullfort": False,
        }
        session = {
            "live_rundeid": "live_123",
            "source_rundeid": "20260101",
            "antall_runder": 2,
            "spillere": [{"spiller": "Tore", "gruppe": 1}, {"spiller": "Ola", "gruppe": 2}],
            "rundeoppsett": [round_setup],
        }
        mock_get_access.return_value = {"session": session, "gruppe": 1, "spillere": ["Tore"]}
        mock_get_live_rounds_df.return_value = pd.DataFrame({"live_rundeid": ["live_123"], "rundeoppsett": ["[]"]})

        next_round_number = advance_to_next_live_round("live_123", "Tore")

        self.assertEqual(next_round_number, 2)
        self.assertTrue(round_setup["fullfort"])
        self.assertEqual(len(session["rundeoppsett"]), 2)
        new_round = session["rundeoppsett"][1]
        self.assertEqual(new_round["runde"], 2)
        self.assertFalse(new_round["fullfort"])
        # Tore: 0 + (3+4) - (3+4) = 0 | Ola: 0 + (4+5) - (3+4) = 2
        self.assertEqual(new_round["startverdier"], {"Tore": 0, "Ola": 2})
        saved_score_df = mock_save_table_df.call_args_list[0].args[1]
        self.assertEqual(saved_score_df["hull"].tolist(), [1, 2])
        self.assertTrue(saved_score_df["Tore"].isna().all())

    @patch("aiapi.live_round.get_live_round_access")
    def test_advance_to_next_live_round_rejects_when_no_more_rounds(self, mock_get_access):
        round_setup = {"runde": 1, "startverdier": {}, "gruppe_klar": {"1": [], "2": []}, "fullfort": False}
        session = {"antall_runder": 1, "spillere": [], "rundeoppsett": [round_setup], "source_rundeid": "20260101"}
        mock_get_access.return_value = {"session": session, "gruppe": 1, "spillere": []}

        with self.assertRaisesRegex(LiveRoundError, "ingen flere runder"):
            advance_to_next_live_round("live_123", "Tore")


if __name__ == "__main__":
    unittest.main()