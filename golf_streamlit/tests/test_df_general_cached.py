import unittest
from unittest.mock import patch

import pandas as pd
import streamlit as st

from aiapi.df_general_cached import clear_cached_df, get_cached_df, set_cached_df


class DataFrameCacheTests(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()

    def test_set_cached_df_stores_df_and_updates_log(self):
        df = pd.DataFrame({"a": [1]})

        set_cached_df("spillere", df)

        self.assertTrue(st.session_state.cached_dfs["spillere"].equals(df))
        self.assertEqual(st.session_state.df_change_log[0]["df_name"], "spillere")

    @patch("aiapi.df_general_cached.get_sqlite_df")
    def test_get_cached_df_loads_once_from_sqlite(self, get_sqlite_df_mock):
        get_sqlite_df_mock.return_value = pd.DataFrame({"a": [1]})

        first_df = get_cached_df("rundeinfo")
        second_df = get_cached_df("rundeinfo")

        get_sqlite_df_mock.assert_called_once_with("rundeinfo")
        self.assertTrue(first_df.equals(second_df))

    def test_clear_cached_df_removes_cached_entry(self):
        set_cached_df("rundeinfo", pd.DataFrame({"a": [1]}))

        clear_cached_df("rundeinfo")

        self.assertNotIn("rundeinfo", st.session_state.cached_dfs)


if __name__ == "__main__":
    unittest.main()