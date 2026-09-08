import base64
from pathlib import Path

import streamlit as st


AUTH_SESSION_KEY = "auth_logged_in_ind"
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
    st.session_state.pop(AUTH_SESSION_KEY, None)
    st.session_state.pop("innlogget_spiller", None)
    st.session_state.pop("welcome_toast_player", None)
    st.session_state.pop("choosen_mainpage", None)
    st.session_state.pop("choosen_subpage", None)


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


def require_login_page(stop: bool = True) -> str | None:
    logged_in_player = get_logged_in_player()
    if logged_in_player is not None:
        return logged_in_player

    _render_login_logo()

    login_column = st.columns([1, 2, 1])[1]
    with login_column:
        with st.form("login_form"):
            password = st.text_input(
                "Passord",
                type="password",
                placeholder="Passord",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button(
                "Fortsett",
                type="primary",
                width="stretch",
                disabled=not st.session_state.get("sqlite_bootstrap_checked", False),
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
                st.success(f"Innlogget som {player_name}")
                st.rerun()

    if stop:
        st.stop()
    return None