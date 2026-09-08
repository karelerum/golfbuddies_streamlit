import unittest
import sys
import types
from unittest.mock import patch

import pandas as pd

fake_gsheet_module = types.ModuleType("aiapi.gsheet")
fake_gsheet_module.create_worksheet_if_missing = lambda *args, **kwargs: None
fake_gsheet_module.df_to_sheet = lambda *args, **kwargs: None
fake_gsheet_module.sheet_to_df = lambda *args, **kwargs: pd.DataFrame()
fake_gsheet_module.batch_sheets_to_dfs = lambda *args, **kwargs: {}
fake_gsheet_module.list_worksheets = lambda *args, **kwargs: []
fake_gsheet_module.delete_worksheet_if_exists = lambda *args, **kwargs: False
fake_gsheet_module.ensure_gsheet_audit_baseline = lambda *args, **kwargs: None
fake_gsheet_module.get_latest_gsheet_audit_timestamp = lambda *args, **kwargs: None
fake_gsheet_module.is_internal_worksheet_name = lambda title: str(title).strip().lower() == "audit_log"
sys.modules.setdefault("aiapi.gsheet", fake_gsheet_module)

from aiapi.gsheet_sync import (
    SyncReport,
    _format_sync_error,
    _get_sheet_url_for_source,
    ensure_sqlite_seeded_from_gsheet,
    sqlite_needs_gsheet_bootstrap,
    sync_all_gsheets_to_sqlite,
    sync_df_to_gsheet,
    sync_sheets_to_sqlite,
    sync_worksheet_list_to_sqlite,
)


class SyncReportTests(unittest.TestCase):
    def test_live_rounds_source_uses_dedicated_spreadsheet(self):
        sheet_url, source_name = _get_sheet_url_for_source("live_rounds")

        self.assertIn("1x_9lLCV8o2x2YnKSESjZzcDSMMowm6-1ObWjetVtegU", sheet_url)
        self.assertEqual(source_name, "live_rounds")

    def test_status_message_without_issues(self):
        report = SyncReport()
        self.assertEqual(report.status_message(), "Synkronisering fullført uten feil.")

    def test_status_message_with_error_and_warning(self):
        report = SyncReport()
        report.add_issue("error", "master/sheet", "Boom", "rundeinfo")
        report.add_issue("warning", "worksheet_list/master", "Lite problem", "rundeinfo")
        self.assertEqual(report.status_message(), "Synkronisering fullført med 1 feil og 1 advarsler.")

    def test_format_sync_error_translates_quota_message(self):
        message = _format_sync_error(Exception("APIError: [429]: Quota exceeded for quota metric 'Read requests' and limit 'Read requests per minute per user' of service 'sheets.googleapis.com'"))
        self.assertIn("Google Sheets-kvote overskredet", message)
        self.assertIn("Read requests per minute per user", message)


class WorksheetListSyncTests(unittest.TestCase):
    @patch("aiapi.gsheet_sync.replace_sqlite_table_from_df", return_value=False)
    @patch("aiapi.gsheet_sync.list_worksheets", side_effect=[["rundeinfo"], ["20240101"]])
    def test_sync_worksheet_list_reports_save_failure(self, _list_worksheets, _replace):
        report = sync_worksheet_list_to_sqlite()
        self.assertFalse(report.ok)
        self.assertTrue(any(issue.stage == "worksheet_list/save" for issue in report.issues))

    @patch("aiapi.gsheet_sync.list_worksheets", side_effect=[Exception("APIError: [429]: Quota exceeded for quota metric 'Read requests' and limit 'Read requests per minute per user' of service 'sheets.googleapis.com'"), ["20240101"]])
    def test_sync_worksheet_list_formats_quota_error(self, _list_worksheets):
        report = sync_worksheet_list_to_sqlite()
        self.assertFalse(report.ok)
        self.assertIn("Google Sheets-kvote overskredet", report.issues[0].message)


class SheetSyncTests(unittest.TestCase):
    @patch("aiapi.gsheet_sync.replace_sqlite_table_from_df", return_value=True)
    @patch(
        "aiapi.gsheet_sync.batch_sheets_to_dfs",
        return_value={"tomt": pd.DataFrame(), "ok": pd.DataFrame({"a": [1]})},
    )
    @patch("aiapi.gsheet_sync.list_worksheets", return_value=["tomt", "ok"])
    def test_sync_sheets_reports_empty_sheet_as_warning(self, _list_worksheets, _batch_sheets_to_dfs, _replace):
        report = sync_sheets_to_sqlite("dummy", "master")
        self.assertTrue(report.ok)
        self.assertEqual(report.warning_count, 1)
        self.assertEqual(report.issues[0].sheet_name, "tomt")

    @patch("aiapi.gsheet_sync.batch_sheets_to_dfs", side_effect=Exception("APIError: [429]: Quota exceeded for quota metric 'Read requests'"))
    @patch("aiapi.gsheet_sync.list_worksheets", return_value=["rundeinfo"])
    def test_sync_sheets_reports_batch_read_error(self, _list_worksheets, _batch_sheets_to_dfs):
        report = sync_sheets_to_sqlite("dummy", "master")
        self.assertFalse(report.ok)
        self.assertEqual(report.issues[0].stage, "master/batch_read")


class SingleSheetSyncTests(unittest.TestCase):
    @patch("aiapi.gsheet_sync.df_to_sheet")
    def test_sync_df_to_gsheet_writes_df(self, write_mock):
        df = pd.DataFrame({"a": [1, 2]})
        report = sync_df_to_gsheet(df, "master", "min_test")

        self.assertTrue(report.ok)
        write_mock.assert_called_once()

    @patch("aiapi.gsheet_sync.df_to_sheet", side_effect=Exception("boom"))
    def test_sync_df_to_gsheet_reports_write_error(self, write_mock):
        df = pd.DataFrame({"a": [1]})
        report = sync_df_to_gsheet(df, "rounds", "20260101")

        self.assertFalse(report.ok)
        self.assertEqual(report.issues[0].stage, "rounds/write")
        write_mock.assert_called_once()

    def test_sync_df_to_gsheet_uses_df_attrs_for_worksheet_name(self):
        df = pd.DataFrame({"a": [1]})
        df.attrs["worksheet"] = "fra_attrs"

        with patch("aiapi.gsheet_sync.df_to_sheet") as write_mock:
            report = sync_df_to_gsheet(df, "master")

        self.assertTrue(report.ok)
        write_mock.assert_called_once()

    def test_sync_df_to_gsheet_rejects_unknown_source(self):
        with self.assertRaisesRegex(ValueError, "Ugyldig source"):
            sync_df_to_gsheet(pd.DataFrame({"a": [1]}), "annet", "test")


class SyncAllTests(unittest.TestCase):
    @patch("aiapi.gsheet_sync.ensure_gsheet_audit_baseline")
    @patch("aiapi.gsheet_sync.sync_rounds_sheets_to_sqlite")
    @patch("aiapi.gsheet_sync.sync_master_sheets_to_sqlite")
    @patch("aiapi.gsheet_sync.sync_worksheet_list_to_sqlite")
    def test_sync_all_merges_reports(self, worksheet_mock, master_mock, rounds_mock, audit_baseline_mock):
        worksheet_report = SyncReport()
        worksheet_report.add_issue("warning", "worksheet_list", "Varsel")
        master_report = SyncReport()
        rounds_report = SyncReport()
        rounds_report.add_issue("error", "rounds/sheet", "Feil", "20240101")

        worksheet_mock.return_value = worksheet_report
        master_mock.return_value = master_report
        rounds_mock.return_value = rounds_report

        report = sync_all_gsheets_to_sqlite()

        self.assertFalse(report.ok)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.warning_count, 1)
        audit_baseline_mock.assert_not_called()

    @patch("aiapi.gsheet_sync.ensure_gsheet_audit_baseline")
    @patch("aiapi.gsheet_sync.sync_rounds_sheets_to_sqlite")
    @patch("aiapi.gsheet_sync.sync_master_sheets_to_sqlite")
    @patch("aiapi.gsheet_sync.sync_worksheet_list_to_sqlite")
    def test_sync_all_runs_master_rounds_and_worksheet_sync_on_success(self, worksheet_mock, master_mock, rounds_mock, audit_baseline_mock):
        worksheet_mock.return_value = SyncReport()
        master_mock.return_value = SyncReport()
        rounds_mock.return_value = SyncReport()

        report = sync_all_gsheets_to_sqlite()

        self.assertTrue(report.ok)
        worksheet_mock.assert_called_once_with()
        master_mock.assert_called_once_with()
        rounds_mock.assert_called_once_with()
        self.assertEqual(audit_baseline_mock.call_count, 2)

    @patch("aiapi.gsheet_sync.ensure_gsheet_audit_baseline", side_effect=[RuntimeError("Google Sheets-kvote truffet under lesing for audit-kolonne 'VO_Data': APIError: [429]: Quota exceeded for quota metric 'Read requests'") , RuntimeError("Google Sheets-kvote truffet under lesing for audit-kolonne 'VO_Data': APIError: [429]: Quota exceeded for quota metric 'Read requests'")])
    @patch("aiapi.gsheet_sync.sync_rounds_sheets_to_sqlite")
    @patch("aiapi.gsheet_sync.sync_master_sheets_to_sqlite")
    @patch("aiapi.gsheet_sync.sync_worksheet_list_to_sqlite")
    def test_sync_all_downgrades_audit_baseline_quota_to_warning(self, worksheet_mock, master_mock, rounds_mock, audit_baseline_mock):
        worksheet_mock.return_value = SyncReport()
        master_mock.return_value = SyncReport()
        rounds_mock.return_value = SyncReport()

        report = sync_all_gsheets_to_sqlite()

        self.assertTrue(report.ok)
        self.assertEqual(report.warning_count, 2)
        self.assertEqual(audit_baseline_mock.call_count, 2)


class BootstrapSyncTests(unittest.TestCase):
    @patch("aiapi.gsheet_sync.table_exists", return_value=True)
    @patch("aiapi.gsheet_sync.get_table_row_count", return_value=1)
    @patch("aiapi.gsheet_sync.get_latest_sqlite_audit_timestamp", return_value=None)
    @patch("aiapi.gsheet_sync.sync_all_gsheets_to_sqlite")
    def test_bootstrap_sync_runs_when_sqlite_has_no_audit_log(self, sync_all_mock, _latest_sqlite, _row_count, _table_exists):
        sync_report = SyncReport()
        sync_all_mock.return_value = sync_report

        report = ensure_sqlite_seeded_from_gsheet()

        self.assertIs(report, sync_report)
        sync_all_mock.assert_called_once_with()

    @patch("aiapi.gsheet_sync.table_exists", return_value=True)
    @patch("aiapi.gsheet_sync.get_table_row_count", return_value=1)
    @patch("aiapi.gsheet_sync.get_latest_gsheet_change_timestamp", return_value="2026-08-02T10:05:00")
    @patch("aiapi.gsheet_sync.get_latest_sqlite_audit_timestamp", return_value="2026-08-02T10:00:00")
    @patch("aiapi.gsheet_sync.sync_all_gsheets_to_sqlite")
    def test_bootstrap_sync_runs_when_gsheet_is_newer_than_sqlite(self, sync_all_mock, _latest_sqlite, _latest_gsheet, _row_count, _table_exists):
        sync_report = SyncReport()
        sync_all_mock.return_value = sync_report

        report = ensure_sqlite_seeded_from_gsheet()

        self.assertIs(report, sync_report)
        sync_all_mock.assert_called_once_with()

    @patch("aiapi.gsheet_sync.table_exists", return_value=True)
    @patch("aiapi.gsheet_sync.get_table_row_count", return_value=1)
    @patch("aiapi.gsheet_sync.get_latest_gsheet_change_timestamp", return_value="2026-08-02T10:00:00")
    @patch("aiapi.gsheet_sync.get_latest_sqlite_audit_timestamp", return_value="2026-08-02T10:00:00")
    @patch("aiapi.gsheet_sync.sync_all_gsheets_to_sqlite")
    def test_bootstrap_sync_skips_when_sqlite_equals_gsheet_audit(self, sync_all_mock, _latest_sqlite, _latest_gsheet, _row_count, _table_exists):
        report = ensure_sqlite_seeded_from_gsheet()

        self.assertTrue(report.ok)
        self.assertEqual(report.issues, [])
        sync_all_mock.assert_not_called()

    @patch("aiapi.gsheet_sync.table_exists", return_value=True)
    @patch("aiapi.gsheet_sync.get_table_row_count", return_value=0)
    @patch("aiapi.gsheet_sync.get_latest_gsheet_change_timestamp", return_value="2026-08-02T10:00:00")
    @patch("aiapi.gsheet_sync.get_latest_sqlite_audit_timestamp", return_value="2026-08-02T10:00:00")
    @patch("aiapi.gsheet_sync.sync_all_gsheets_to_sqlite")
    def test_bootstrap_sync_runs_when_worksheet_list_is_empty(self, sync_all_mock, _latest_sqlite, _latest_gsheet, _row_count, _table_exists):
        sync_report = SyncReport()
        sync_all_mock.return_value = sync_report

        report = ensure_sqlite_seeded_from_gsheet()

        self.assertIs(report, sync_report)
        sync_all_mock.assert_called_once_with()

    @patch("aiapi.gsheet_sync.get_latest_gsheet_change_timestamp", return_value="2026-08-02T10:00:00")
    @patch("aiapi.gsheet_sync.get_latest_sqlite_audit_timestamp", return_value="2026-08-02T10:05:00")
    @patch("aiapi.gsheet_sync.table_exists", return_value=False)
    def test_bootstrap_sync_runs_when_worksheet_list_is_missing(self, _table_exists, _latest_sqlite, _latest_gsheet):
        self.assertTrue(sqlite_needs_gsheet_bootstrap())

    @patch("aiapi.gsheet_sync.get_latest_gsheet_change_timestamp", return_value=None)
    @patch("aiapi.gsheet_sync.get_latest_sqlite_audit_timestamp", return_value="2026-08-02T10:05:00")
    def test_bootstrap_sync_runs_when_gsheet_has_no_audit_log(self, _latest_sqlite, _latest_gsheet):
        self.assertTrue(sqlite_needs_gsheet_bootstrap())

if __name__ == "__main__":
    unittest.main()