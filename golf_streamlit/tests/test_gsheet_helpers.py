import unittest
from unittest.mock import Mock, patch

import pandas as pd
from gspread.exceptions import WorksheetNotFound

from aiapi.gsheet import _df_to_values_list, _get_or_create_worksheet, batch_sheets_to_dfs


class GSheetSerializationTests(unittest.TestCase):
    def test_df_to_values_list_writes_missing_values_as_blank_cells(self):
        df = pd.DataFrame(
            {
                "Doff": pd.Series([pd.NA, 5], dtype="Int64"),
                "Tore": [None, ""],
                "Even": ["<NA>", "nan"],
            }
        )

        values = _df_to_values_list(df)

        self.assertEqual(values, [["", "", ""], ["5", "", ""]])


class GSheetBatchReadTests(unittest.TestCase):
    @patch("aiapi.gsheet._open_spreadsheet")
    @patch("aiapi.gsheet.get_gspread_client")
    def test_batch_sheets_to_dfs_reads_multiple_sheets_in_one_call(self, _get_client, open_spreadsheet_mock):
        spreadsheet = Mock()
        spreadsheet.title = "master"
        spreadsheet.values_batch_get.return_value = {
            "valueRanges": [
                {"values": [["hull", "par"], ["1", "4"], ["2", "3"]]},
                {"values": []},
            ]
        }
        open_spreadsheet_mock.return_value = spreadsheet

        result = batch_sheets_to_dfs("dummy_url", ["hullinfo", "tomt"])

        spreadsheet.values_batch_get.assert_called_once_with(["'hullinfo'", "'tomt'"])
        self.assertEqual(result["hullinfo"]["par"].tolist(), [4, 3])
        self.assertTrue(result["tomt"].empty)

    @patch("aiapi.gsheet._open_spreadsheet")
    @patch("aiapi.gsheet.get_gspread_client")
    @patch("aiapi.gsheet.BATCH_READ_CHUNK_SIZE", 1)
    def test_batch_sheets_to_dfs_chunks_large_worksheet_lists(self, _get_client, open_spreadsheet_mock):
        spreadsheet = Mock()
        spreadsheet.title = "rounds"
        spreadsheet.values_batch_get.side_effect = [
            {"valueRanges": [{"values": [["hull"], ["1"]]}]},
            {"valueRanges": [{"values": [["hull"], ["2"]]}]},
        ]
        open_spreadsheet_mock.return_value = spreadsheet

        result = batch_sheets_to_dfs("dummy_url", ["20260101", "20260102"])

        self.assertEqual(spreadsheet.values_batch_get.call_count, 2)
        self.assertEqual(result["20260101"]["hull"].tolist(), [1])
        self.assertEqual(result["20260102"]["hull"].tolist(), [2])

    def test_batch_sheets_to_dfs_returns_empty_dict_for_no_titles(self):
        self.assertEqual(batch_sheets_to_dfs("dummy_url", []), {})


class GSheetAuditTests(unittest.TestCase):
    @patch("aiapi.gsheet._cached_list_worksheets")
    @patch("aiapi.gsheet._append_data_write_audit_row")
    @patch("aiapi.gsheet._run_gsheet_call")
    @patch("aiapi.gsheet._get_worksheet", side_effect=WorksheetNotFound("missing"))
    def test_create_worksheet_logs_audit_event(self, _get_worksheet_mock, run_call_mock, append_audit_mock, cached_list_mock):
        spreadsheet = Mock()
        spreadsheet.title = "VO_Data"

        created_ws = Mock()
        created_ws.title = "20261224"
        run_call_mock.return_value = created_ws

        worksheet = _get_or_create_worksheet(spreadsheet, "20261224")

        self.assertIs(worksheet, created_ws)
        append_audit_mock.assert_called_once_with(spreadsheet, "20261224", "create_worksheet")
        cached_list_mock.cache_clear.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()