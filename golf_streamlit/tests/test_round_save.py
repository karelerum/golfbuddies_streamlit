import unittest
from unittest.mock import patch

import pandas as pd

from aiapi.round_save import RoundSaveError, save_round_and_sync
from aiapi.gsheet_sync import SyncReport


class RoundSaveTests(unittest.TestCase):
    @patch("aiapi.round_save.set_cached_df")
    @patch("aiapi.round_save.my_dfs.save_table_df", return_value=True)
    @patch("aiapi.round_save.badge_calc.calculate_achievements")
    @patch("aiapi.round_save.sync_df_to_gsheet")
    @patch("aiapi.round_save.add_or_update_round_to_result")
    @patch("aiapi.round_save.my_dfs.save_round_info_df", return_value=True)
    @patch("aiapi.round_save.my_dfs.save_round_df", return_value=True)
    @patch(
        "aiapi.round_save.my_dfs.get_round_info_df",
        return_value=pd.DataFrame({"rundeid": ["20260101"], "ferdig_ind": [0], "paagaaende_ind": [1]}),
    )
    def test_save_round_and_sync_returns_sync_report(
        self,
        _get_round_info_df,
        _save_round_df,
        _save_round_info_df,
        add_result_mock,
        sync_mock,
        badge_calc_mock,
        _save_table_df,
        _set_cached_df,
    ):
        sync_mock.return_value = SyncReport()
        add_result_mock.return_value = pd.DataFrame({"rundeid": ["20260101"], "hull": [1], "spiller": ["Tore"]})
        badge_calc_mock.return_value = pd.DataFrame(
            {
                "spiller": ["Tore"],
                "rundeid": ["20260101"],
                "turneringsid": ["T1"],
                "merke_id": [1],
                "vinner_innen": ["runde"],
                "visningsnavn": ["Test"],
                "filnavn": ["test.png"],
            }
        )
        prepared_df = pd.DataFrame({"hull": [1], "Tore": [4]})
        edited_df = pd.DataFrame({"hull": [1], "Tore": [5]})

        result = save_round_and_sync("20260101", prepared_df, edited_df, True)

        self.assertTrue(result.sync_report.ok)
        self.assertEqual(result.round_df.loc[0, "Tore"], 5)
        self.assertEqual(sync_mock.call_count, 4)

    @patch("aiapi.round_save.my_dfs.save_round_info_df", return_value=True)
    @patch("aiapi.round_save.my_dfs.save_round_df", return_value=False)
    @patch(
        "aiapi.round_save.my_dfs.get_round_info_df",
        return_value=pd.DataFrame({"rundeid": ["20260101"], "ferdig_ind": [0], "paagaaende_ind": [1]}),
    )
    def test_save_round_and_sync_wraps_save_failure(self, _get_round_info_df, _save_round_df, _save_round_info_df):
        prepared_df = pd.DataFrame({"hull": [1], "Tore": [4]})
        edited_df = pd.DataFrame({"hull": [1], "Tore": [5]})

        with self.assertRaisesRegex(RoundSaveError, "Klarte ikke å lagre runde 20260101"):
            save_round_and_sync("20260101", prepared_df, edited_df, True)

    @patch("aiapi.round_save.add_or_update_round_to_result", side_effect=ValueError("boom"))
    @patch("aiapi.round_save.my_dfs.save_round_info_df", return_value=True)
    @patch("aiapi.round_save.my_dfs.save_round_df", return_value=True)
    @patch(
        "aiapi.round_save.my_dfs.get_round_info_df",
        return_value=pd.DataFrame({"rundeid": ["20260101"], "ferdig_ind": [0], "paagaaende_ind": [1]}),
    )
    def test_save_round_and_sync_wraps_result_rebuild_failure(
        self,
        _get_round_info_df,
        _save_round_df,
        _save_round_info_df,
        _add_result,
    ):
        prepared_df = pd.DataFrame({"hull": [1], "Tore": [4]})
        edited_df = pd.DataFrame({"hull": [1], "Tore": [5]})

        with self.assertRaisesRegex(RoundSaveError, "resultat kunne ikke oppdateres"):
            save_round_and_sync("20260101", prepared_df, edited_df, True)


if __name__ == "__main__":
    unittest.main()