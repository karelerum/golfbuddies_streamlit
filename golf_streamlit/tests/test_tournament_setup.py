import unittest
from unittest.mock import patch

import pandas as pd

from aiapi import tournament_setup


class TournamentSetupTests(unittest.TestCase):
    @patch(
        "aiapi.tournament_setup.my_dfs.get_tournament_info_df",
        return_value=pd.DataFrame({"turneringsid": ["202601", "202602", "202501"]}),
    )
    def test_get_next_tournament_id_increments_within_year(self, _get_tournament_info_df):
        self.assertEqual(tournament_setup.get_next_tournament_id(2026), "202603")

    @patch(
        "aiapi.tournament_setup.my_dfs.get_round_info_df",
        return_value=pd.DataFrame(
            {
                "turneringsid": ["202601", "202601", "202602"],
                "rundeid": ["20260101", "20260102", "20260201"],
                "runde": [2, 1, 1],
                "bane": ["Fana", "Meland", "Bergen"],
            }
        ),
    )
    def test_get_tournament_rounds_sorts_by_round_then_id(self, _get_round_info_df):
        rounds = tournament_setup.get_tournament_rounds("202601")

        self.assertEqual(
            rounds,
            [
                {"rundeid": "20260102", "runde": 1, "bane": "Meland"},
                {"rundeid": "20260101", "runde": 2, "bane": "Fana"},
            ],
        )

    def test_normalize_round_items_allocates_missing_round_ids(self):
        items = tournament_setup._normalize_round_items(
            "202601",
            [{"rundeid": "20260101", "bane": "Meland"}, {"rundeid": None, "bane": "Fana"}],
        )

        self.assertEqual(items[1], {"rundeid": "20260102", "bane": "Fana"})


if __name__ == "__main__":
    unittest.main()