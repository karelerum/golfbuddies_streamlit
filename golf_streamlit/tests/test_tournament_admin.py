import unittest
from unittest.mock import patch

from aiapi.tournament_admin import (
    TournamentAdminError,
    create_tournament_action,
    delete_tournament_action,
    update_tournament_action,
)
from aiapi.gsheet_sync import SyncReport


class TournamentAdminTests(unittest.TestCase):
    def test_create_tournament_action_requires_name(self):
        with self.assertRaisesRegex(TournamentAdminError, "Turneringsnavn mangler"):
            create_tournament_action("", "Vinter", 2026, ["Tore"], ["Meland"])

    def test_update_tournament_action_requires_players(self):
        with self.assertRaisesRegex(TournamentAdminError, "Velg minst én spiller"):
            update_tournament_action("202601", "VO 26", "Vinter", [], [{"bane": "Meland"}])

    @patch("aiapi.tournament_admin.create_tournament_with_rounds")
    def test_create_tournament_action_returns_success_message(self, create_mock):
        create_mock.return_value = ("202601", SyncReport())

        result = create_tournament_action("VO 26", "Vinter", 2026, ["Tore"], ["Meland"])

        self.assertEqual(result.message, "Turnering opprettet: 202601")
        self.assertTrue(result.ok)

    @patch("aiapi.tournament_admin.update_tournament_with_rounds")
    def test_update_tournament_action_wraps_backend_errors(self, update_mock):
        update_mock.side_effect = ValueError("boom")

        with self.assertRaisesRegex(TournamentAdminError, "Klarte ikke å oppdatere turnering 202601"):
            update_tournament_action("202601", "VO 26", "Vinter", ["Tore"], [{"bane": "Meland"}])

    @patch("aiapi.tournament_admin.delete_tournament")
    def test_delete_tournament_action_returns_result(self, delete_mock):
        report = SyncReport()
        report.add_issue("warning", "tournament/delete", "Lite problem")
        delete_mock.return_value = report

        result = delete_tournament_action("202601")

        self.assertEqual(result.message, "Turnering slettet: 202601")
        self.assertEqual(result.notice_level, "warning")


if __name__ == "__main__":
    unittest.main()