import streamlit as st

from aiapi.auth import PASSWORD_LOGIN_EVENT_KEY, require_login_page
from aiapi.gsheet_sync import sync_all_gsheets_to_sqlite
from aiapi.sqlite import delete_expired_auth_tokens, is_sqlite_ready_for_app
import ui.components.visuals as v
from ui.components.theme import apply_global_styles
import ui.pages.hjem as mainpage_hjem
import ui.pages.live_runde as mainpage_live_runde
import ui.pages_adm.adm as mainpage_adm
import ui.pages.registrer_slag as mainpage_registrer_slag
import ui.pages.spiller as mainpage_spiller


SQLITE_BOOTSTRAP_SESSION_KEY = "sqlite_bootstrap_checked"
SQLITE_LOGIN_PREFLIGHT_STARTED_KEY = "sqlite_login_preflight_started"


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

MAIN_PAGES = {
    "Hjem": mainpage_hjem.page,
    "Registrer slag": mainpage_registrer_slag.page,
    "Live Runde": mainpage_live_runde.page,
    "Spiller": mainpage_spiller.page,
    "Adm": mainpage_adm.page,
}

# A valid cookie returns before the login callback, so it never loads the logo or checks/reloads SQLite.
current_player = require_login_page(stop=False, before_login=ensure_sqlite_ready_for_login)
if current_player is None:
    st.stop()

delete_expired_auth_tokens()

if st.session_state.pop(PASSWORD_LOGIN_EVENT_KEY, False):
    st.toast(f"Velkommen {current_player}", icon=":material/waving_hand:")

v.hoved_navbar(["Hjem", "Registrer slag", "Live Runde", "Spiller"], current_player)
selected_page = MAIN_PAGES.get(st.session_state.choosen_mainpage)
if selected_page is not None:
    selected_page()