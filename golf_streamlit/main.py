import streamlit as st

from aiapi.auth import PASSWORD_LOGIN_EVENT_KEY, require_login_page
from aiapi.sqlite import delete_expired_auth_tokens, is_sqlite_ready_for_app
from ui.components.html_visuals import live_round_session
from ui.components.live_session import build_live_round_session_payload, validate_live_round_session_payload
from ui.components.theme import apply_global_styles


SQLITE_BOOTSTRAP_SESSION_KEY = "sqlite_bootstrap_checked"
SQLITE_LOGIN_PREFLIGHT_STARTED_KEY = "sqlite_login_preflight_started"
LIVE_SESSION_RESTORED_KEY = "live_session_restored"


def ensure_sqlite_ready_for_login() -> bool:
    """Sjekk lokal state før manuell login, og bruk Sheets kun som recovery."""
    if st.session_state.get(SQLITE_BOOTSTRAP_SESSION_KEY):
        return True

    if not st.session_state.get(SQLITE_LOGIN_PREFLIGHT_STARTED_KEY):
        st.session_state[SQLITE_LOGIN_PREFLIGHT_STARTED_KEY] = True
        st.rerun()

    if is_sqlite_ready_for_app():
        st.session_state[SQLITE_BOOTSTRAP_SESSION_KEY] = True
        return True

    from aiapi.gsheet_sync import sync_all_gsheets_to_sqlite

    with st.spinner("Gjenoppretter lokale data fra Google Sheets ..."):
        bootstrap_report = sync_all_gsheets_to_sqlite()

    if not bootstrap_report.ok:
        st.error(bootstrap_report.status_message())
        with st.expander("Vis sync-detaljer"):
            for issue in bootstrap_report.issues:
                st.write(f"- {issue.to_display_text()}")
        return False

    st.session_state[SQLITE_BOOTSTRAP_SESSION_KEY] = True

    if bootstrap_report.warning_count:
        st.warning(bootstrap_report.status_message())

    return True


st.set_page_config(page_title="Golf Streamlit", layout="wide")
apply_global_styles()

# A valid cookie returns before the login callback, so it never loads the logo or checks/reloads SQLite.
current_player = require_login_page(stop=False, before_login=ensure_sqlite_ready_for_login)
if current_player is None:
    st.stop()

delete_expired_auth_tokens()

current_mainpage = st.session_state.get("choosen_mainpage")
live_session_payload = build_live_round_session_payload(st.session_state, current_player)
clear_live_session = current_mainpage is not None and (
    current_mainpage != "Live Runde" or live_session_payload is None
)
stored_live_session = live_round_session(
    payload=live_session_payload,
    clear=clear_live_session,
)
if not isinstance(stored_live_session, dict) or not stored_live_session.get("ready"):
    st.stop()

if not st.session_state.get(LIVE_SESSION_RESTORED_KEY):
    restored_live_session = validate_live_round_session_payload(stored_live_session.get("payload"), current_player)
    st.session_state[LIVE_SESSION_RESTORED_KEY] = True
    if restored_live_session and not clear_live_session:
        st.session_state.update(
            choosen_mainpage="Live Runde",
            live_session_id=restored_live_session["live_rundeid"],
            live_runde_view=restored_live_session["live_runde_view"],
            live_open_next_hole_for=restored_live_session["live_rundeid"],
        )
        if "live_active_group" in restored_live_session:
            st.session_state.live_active_group = restored_live_session["live_active_group"]
        st.rerun()

if st.session_state.pop(PASSWORD_LOGIN_EVENT_KEY, False):
    st.toast(f"Velkommen {current_player}", icon=":material/waving_hand:")

with st.spinner("Laster ...", show_time=False):
    import ui.components.visuals as v

    v.hoved_navbar(["Hjem", "Registrer slag", "Live Runde", "Spiller"], current_player)

    selected_page_name = st.session_state.choosen_mainpage
    if selected_page_name == "Hjem":
        from ui.pages.hjem import page
    elif selected_page_name == "Registrer slag":
        from ui.pages.registrer_slag import page
    elif selected_page_name == "Live Runde":
        from ui.pages.live_runde import page
    elif selected_page_name == "Spiller":
        from ui.pages.spiller import page
    elif selected_page_name == "Adm":
        from ui.pages_adm.adm import page
    else:
        page = None

    if page is not None:
        page()