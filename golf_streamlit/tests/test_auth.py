import unittest
from unittest.mock import patch

import streamlit as st

from aiapi.auth import AUTH_SESSION_KEY, AuthConfigError, get_logged_in_player, get_password_map, is_logged_in, login_with_password, logout


class AuthTests(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()

    @patch("aiapi.auth.st.secrets", {"auth": {"passwords": {"Kåre": "abc", "Tore": "xyz"}}})
    def test_get_password_map_reads_auth_passwords(self):
        self.assertEqual(get_password_map()["Kåre"], "abc")

    @patch("aiapi.auth.st.secrets", {"auth": {"passwords": {"Kåre": "abc", "Tore": "xyz"}}})
    def test_login_with_password_sets_player(self):
        player_name = login_with_password("xyz")

        self.assertEqual(player_name, "Tore")
        self.assertTrue(st.session_state[AUTH_SESSION_KEY])
        self.assertEqual(get_logged_in_player(), "Tore")
        self.assertTrue(is_logged_in())

    @patch("aiapi.auth.st.secrets", {"auth": {"passwords": {"Kåre": "abc"}}})
    def test_login_with_password_returns_none_for_invalid_password(self):
        self.assertIsNone(login_with_password("wrong"))
        self.assertFalse(is_logged_in())

    def test_get_password_map_raises_clear_error_when_missing(self):
        with patch("aiapi.auth.st.secrets", {}):
            with self.assertRaisesRegex(AuthConfigError, "Fant ikke auth.passwords"):
                get_password_map()

    def test_logout_clears_login_state(self):
        st.session_state[AUTH_SESSION_KEY] = True
        st.session_state["innlogget_spiller"] = "Kåre"
        st.session_state["choosen_mainpage"] = "Hjem"

        logout()

        self.assertIsNone(get_logged_in_player())
        self.assertNotIn(AUTH_SESSION_KEY, st.session_state)
        self.assertNotIn("choosen_mainpage", st.session_state)

    def test_legacy_player_session_without_auth_flag_is_not_logged_in(self):
        st.session_state["innlogget_spiller"] = "Kåre"

        self.assertIsNone(get_logged_in_player())
        self.assertFalse(is_logged_in())


if __name__ == "__main__":
    unittest.main()