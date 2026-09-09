import unittest
from unittest.mock import patch

from aiapi.sqlite import is_sqlite_ready_for_app


class SQLiteReadinessTests(unittest.TestCase):
    @patch("aiapi.sqlite.get_table_row_count", return_value=1)
    @patch("aiapi.sqlite.table_exists", return_value=True)
    def test_ready_when_worksheet_list_has_rows(self, _table_exists, _row_count):
        self.assertTrue(is_sqlite_ready_for_app())

    @patch("aiapi.sqlite.get_table_row_count", return_value=0)
    @patch("aiapi.sqlite.table_exists", return_value=True)
    def test_not_ready_when_worksheet_list_is_empty(self, _table_exists, _row_count):
        self.assertFalse(is_sqlite_ready_for_app())

    @patch("aiapi.sqlite.table_exists", return_value=False)
    def test_not_ready_when_worksheet_list_is_missing(self, _table_exists):
        self.assertFalse(is_sqlite_ready_for_app())


if __name__ == "__main__":
    unittest.main()