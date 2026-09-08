import unittest
from unittest.mock import patch

import pandas as pd

from aiapi.admin_tasks import AdminTaskError, rebuild_result_task, run_full_sync_task, save_master_tables_task
from aiapi.gsheet_sync import SyncReport


class AdminTasksTests(unittest.TestCase):
    @patch("aiapi.admin_tasks.sync_all_gsheets_to_sqlite")
    def test_run_full_sync_task_returns_elapsed_time(self, sync_mock):
        sync_mock.return_value = SyncReport()

        result = run_full_sync_task()

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.elapsed_seconds)

    @patch("aiapi.admin_tasks.rebuild_result_df")
    def test_rebuild_result_task_returns_row_count(self, rebuild_mock):
        rebuild_mock.return_value = (pd.DataFrame({"a": [1, 2]}), SyncReport())

        result = rebuild_result_task()

        self.assertEqual(result.row_count, 2)
        self.assertIn("2 rader", result.message)

    @patch("aiapi.admin_tasks.sync_all_gsheets_to_sqlite", side_effect=ValueError("boom"))
    def test_run_full_sync_task_wraps_errors(self, _sync_mock):
        with self.assertRaisesRegex(AdminTaskError, "Klarte ikke å hente alt fra Google Sheets"):
            run_full_sync_task()

    @patch("aiapi.admin_tasks.sync_df_to_gsheet")
    @patch("aiapi.admin_tasks.my_dfs.save_table_df")
    def test_save_master_tables_task_collects_sync_issues(self, save_mock, sync_mock):
        report = SyncReport()
        report.add_issue("warning", "master/write", "Varsel", "spillere")
        sync_mock.return_value = report

        result = save_master_tables_task({"spillere": pd.DataFrame({"Navn": ["Tore"]})})

        save_mock.assert_called_once()
        self.assertFalse(result.ok)
        self.assertEqual(result.sync_report.warning_count, 1)


if __name__ == "__main__":
    unittest.main()