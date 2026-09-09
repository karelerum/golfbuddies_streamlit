import unittest
from unittest.mock import patch

import streamlit as st

from aiapi.auth import (
    AUTH_SESSION_KEY,
    AuthConfigError,
    _hash_token,
    create_remember_token,
    get_logged_in_player,
    get_password_map,
    is_logged_in,
    login_with_password,
    logout,
    require_login_page,
    try_restore_session_from_cookie,
)


class _FakeCookieManager:
    def __init__(self):
        self._cookies: dict[str, str] = {}

    def get(self, name):
        return self._cookies.get(name)

    def get_all(self):
        return dict(self._cookies)

    def set(self, name, value, expires_at=None):
        self._cookies[name] = value

    def delete(self, name):
        self._cookies.pop(name, None)


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

    @patch("aiapi.auth._get_fresh_cookie_manager")
    @patch("aiapi.auth.try_restore_session_from_cookie", return_value="Tore")
    def test_valid_cookie_skips_login_callback(self, _restore_mock, _cookie_manager_mock):
        readiness_mock = unittest.mock.Mock()

        player_name = require_login_page(stop=False, before_login=readiness_mock)

        self.assertEqual(player_name, "Tore")
        readiness_mock.assert_not_called()


class RememberMeTokenTests(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()
        self.fake_cookie_manager = _FakeCookieManager()
        self.cookie_manager_patch = patch("aiapi.auth._get_cookie_manager", return_value=self.fake_cookie_manager)
        self.cookie_manager_patch.start()
        self.addCleanup(self.cookie_manager_patch.stop)

    @patch("aiapi.auth.get_player_for_token")
    @patch("aiapi.auth.store_auth_token")
    def test_create_remember_token_stores_hash_and_sets_cookie(self, mock_store, mock_get_player):
        raw_token = create_remember_token("Tore")

        stored_hash = mock_store.call_args.args[0]
        self.assertEqual(stored_hash, _hash_token(raw_token))
        self.assertEqual(self.fake_cookie_manager.get("golf_remember_token"), raw_token)

    @patch("aiapi.auth.get_player_for_token", return_value="Tore")
    def test_try_restore_session_from_cookie_logs_in_valid_token(self, mock_get_player):
        self.fake_cookie_manager.set("golf_remember_token", "some-raw-token")

        restored_player = try_restore_session_from_cookie()

        self.assertEqual(restored_player, "Tore")
        self.assertTrue(st.session_state[AUTH_SESSION_KEY])
        self.assertEqual(get_logged_in_player(), "Tore")

    @patch("aiapi.auth.get_player_for_token", return_value=None)
    def test_try_restore_session_from_cookie_rejects_expired_or_unknown_token(self, mock_get_player):
        self.fake_cookie_manager.set("golf_remember_token", "some-raw-token")

        self.assertIsNone(try_restore_session_from_cookie())
        self.assertIsNone(get_logged_in_player())

    def test_try_restore_session_from_cookie_returns_none_without_cookie(self):
        self.assertIsNone(try_restore_session_from_cookie())

    @patch("aiapi.auth.delete_auth_tokens_for_player")
    def test_logout_deletes_token_and_cookie(self, mock_delete_tokens):
        st.session_state[AUTH_SESSION_KEY] = True
        st.session_state["innlogget_spiller"] = "Tore"
        self.fake_cookie_manager.set("golf_remember_token", "some-raw-token")

        logout()

        mock_delete_tokens.assert_called_once_with("Tore")
        self.assertIsNone(self.fake_cookie_manager.get("golf_remember_token"))


if __name__ == "__main__":
    unittest.main()