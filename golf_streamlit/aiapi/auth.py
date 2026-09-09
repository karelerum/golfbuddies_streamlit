import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from collections.abc import Callable

import streamlit as st

from aiapi.sqlite import delete_auth_tokens_for_player, get_player_for_token, store_auth_token
from config.constants import REMEMBER_ME_DAYS


AUTH_SESSION_KEY = "auth_logged_in_ind"
REMEMBER_ME_COOKIE_NAME = "golf_remember_token"
PASSWORD_LOGIN_EVENT_KEY = "auth_password_login_event"
_COOKIE_CHECK_WARMED_UP_KEY = "_cookie_check_warmed_up"
LOGIN_LOGO_VIDEO_PATH = Path(__file__).resolve().parents[1] / "assets" / "vo_logo_gif_2.mp4"


class AuthConfigError(RuntimeError):
    """Raised when auth secrets are missing or malformed."""


def get_password_map() -> dict[str, str]:
    try:
        raw_passwords = st.secrets["auth"]["passwords"]
    except Exception as exc:
        raise AuthConfigError(
            "Fant ikke auth.passwords i Streamlit secrets. Legg inn ett passord per spiller i secrets.toml."
        ) from exc

    password_map = {
        str(player).strip(): str(password)
        for player, password in dict(raw_passwords).items()
        if str(player).strip() and str(password)
    }
    if not password_map:
        raise AuthConfigError("auth.passwords finnes i secrets, men inneholder ingen gyldige spillere.")
    return password_map


def get_logged_in_player() -> str | None:
    if not st.session_state.get(AUTH_SESSION_KEY, False):
        return None

    player_name = st.session_state.get("innlogget_spiller")
    return str(player_name) if player_name else None


def is_logged_in() -> bool:
    return get_logged_in_player() is not None


def login_with_password(password: str) -> str | None:
    normalized_password = str(password or "")
    if not normalized_password:
        return None

    for player_name, player_password in get_password_map().items():
        if normalized_password == player_password:
            st.session_state[AUTH_SESSION_KEY] = True
            st.session_state["innlogget_spiller"] = player_name
            return player_name
    return None


def logout() -> None:
    player_name = st.session_state.get("innlogget_spiller")
    if player_name:
        delete_auth_tokens_for_player(str(player_name))
    try:
        _get_cookie_manager().delete(REMEMBER_ME_COOKIE_NAME)
    except KeyError:
        pass  # no remember-me cookie was set for this browser
    st.session_state.pop(AUTH_SESSION_KEY, None)
    st.session_state.pop("innlogget_spiller", None)
    st.session_state.pop("welcome_toast_player", None)
    st.session_state.pop("choosen_mainpage", None)
    st.session_state.pop("choosen_subpage", None)


def _get_cookie_manager():
    # imported lazily so plain unit tests don't need the component installed/running in a script context
    import extra_streamlit_components as stx

    # constructed once per session (not per rerun): the component key must stay unique within a single run
    if "_remember_me_cookie_manager" not in st.session_state:
        st.session_state["_remember_me_cookie_manager"] = stx.CookieManager(key="golf_cookie_manager")
    return st.session_state["_remember_me_cookie_manager"]


def _get_fresh_cookie_manager():
    """Return the cached cookie manager after refreshing its cookies from the browser for this rerun."""
    cookie_manager = _get_cookie_manager()
    cookie_manager.get_all()
    return cookie_manager


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_remember_token(player_name: str, cookie_manager=None) -> str:
    """Create a 'remember me' token, persist its hash, and store the raw token in a browser cookie."""
    raw_token = secrets.token_urlsafe(32)
    expires_at_dt = datetime.now(UTC) + timedelta(days=REMEMBER_ME_DAYS)
    store_auth_token(_hash_token(raw_token), player_name, expires_at_dt.isoformat(timespec="seconds"))
    (cookie_manager or _get_cookie_manager()).set(REMEMBER_ME_COOKIE_NAME, raw_token, expires_at=expires_at_dt)
    return raw_token


def try_restore_session_from_cookie(cookie_manager=None) -> str | None:
    """Silently log a player back in from a valid 'remember me' cookie, without rendering the login form."""
    raw_token = (cookie_manager or _get_fresh_cookie_manager()).get(REMEMBER_ME_COOKIE_NAME)
    if not raw_token:
        return None

    player_name = get_player_for_token(_hash_token(str(raw_token)))
    if player_name is None:
        return None

    st.session_state[AUTH_SESSION_KEY] = True
    st.session_state["innlogget_spiller"] = player_name
    return player_name


@st.cache_data
def _get_login_logo_video_base64() -> str:
    return base64.b64encode(LOGIN_LOGO_VIDEO_PATH.read_bytes()).decode("ascii")


def _render_login_logo() -> None:
    logo_column = st.columns([1, 4, 1])[1]
    with logo_column:
        video_data = _get_login_logo_video_base64()
        # transform/filter force a different GPU compositing path, which hides a stray render seam on the video's edge
        st.markdown(
            f'''
            <div style="display:flex;justify-content:center;width:100%;">
                <div style="width:480px;max-width:100%;aspect-ratio:4 / 3;overflow:hidden;line-height:0;">
                    <video
                        autoplay loop muted playsinline
                        disablePictureInPicture
                        style="display:block;width:calc(100% + 4px);height:calc(100% + 4px);margin-left:-2px;margin-top:-2px;object-fit:cover;border:0;outline:0;transform:translateZ(0);backface-visibility:hidden;will-change:transform;filter:brightness(1);"
                    >
                        <source src="data:video/mp4;base64,{video_data}" type="video/mp4">
                    </video>
                </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )


def require_login_page(
    stop: bool = True,
    before_login: Callable[[], bool] | None = None,
) -> str | None:
    logged_in_player = get_logged_in_player()
    if logged_in_player is not None:
        return logged_in_player

    cookie_manager = _get_fresh_cookie_manager()
    restored_player = try_restore_session_from_cookie(cookie_manager)
    if restored_player is not None:
        return restored_player

    # the cookie component's real value only arrives after one round trip to the browser; wait for
    # that silently before showing the login screen so a valid "remember me" cookie doesn't flash it
    if not st.session_state.get(_COOKIE_CHECK_WARMED_UP_KEY):
        st.session_state[_COOKIE_CHECK_WARMED_UP_KEY] = True
        st.rerun()

    _render_login_logo()

    login_ready = True if before_login is None else before_login()

    login_column = st.columns([1, 2, 1])[1]
    with login_column:
        with st.form("login_form"):
            password = st.text_input(
                "Passord",
                type="password",
                placeholder="Passord",
                label_visibility="collapsed",
            )
            remember_me = st.checkbox("Husk meg på denne enheten", value=True)
            submitted = st.form_submit_button(
                "Fortsett",
                type="primary",
                width="stretch",
                disabled=not login_ready,
            )

    if submitted:
        try:
            player_name = login_with_password(password)
        except AuthConfigError as exc:
            st.error(str(exc))
        else:
            if player_name is None:
                st.error("Feil passord. Prøv igjen.")
            else:
                if remember_me:
                    create_remember_token(player_name, cookie_manager)
                st.session_state[PASSWORD_LOGIN_EVENT_KEY] = True
                st.success(f"Innlogget som {player_name}")
                st.rerun()

    if stop:
        st.stop()
    return None