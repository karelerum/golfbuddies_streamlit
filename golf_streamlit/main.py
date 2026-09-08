import streamlit as st

from aiapi.auth import require_login_page
from aiapi.gsheet_sync import ensure_sqlite_seeded_from_gsheet
import ui.components.visuals as v
from ui.components.theme import apply_global_styles
import ui.pages.hjem as mainpage_hjem
import ui.pages.live_runde as mainpage_live_runde
import ui.pages_adm.adm as mainpage_adm
import ui.pages.registrer_slag as mainpage_registrer_slag
import ui.pages.spiller as mainpage_spiller


SQLITE_BOOTSTRAP_SESSION_KEY = "sqlite_bootstrap_checked"
WELCOME_TOAST_PLAYER_KEY = "welcome_toast_player"


def ensure_sqlite_ready_for_session() -> None:
    if st.session_state.get(SQLITE_BOOTSTRAP_SESSION_KEY):
        return

    with st.spinner("Henter fra data fra google sheet"):
        bootstrap_report = ensure_sqlite_seeded_from_gsheet()

    if not bootstrap_report.ok:
        st.error(bootstrap_report.status_message())
        with st.expander("Vis sync-detaljer"):
            for issue in bootstrap_report.issues:
                st.write(f"- {issue.to_display_text()}")
        st.stop()

    st.session_state[SQLITE_BOOTSTRAP_SESSION_KEY] = True

    if bootstrap_report.warning_count:
        st.warning(bootstrap_report.status_message())


st.set_page_config(page_title="Golf Streamlit", layout="wide")
apply_global_styles()

MAIN_PAGES = {
    "Hjem": mainpage_hjem.page,
    "Registrer slag": mainpage_registrer_slag.page,
    "Live Runde": mainpage_live_runde.page,
    "Spiller": mainpage_spiller.page,
    "Adm": mainpage_adm.page,
}

current_player = require_login_page(stop=False)
if current_player is None:
    data_was_ready = bool(st.session_state.get(SQLITE_BOOTSTRAP_SESSION_KEY))
    ensure_sqlite_ready_for_session()
    if not data_was_ready:
        st.rerun()
    st.stop()

ensure_sqlite_ready_for_session()

if st.session_state.get(WELCOME_TOAST_PLAYER_KEY) != current_player:
    st.toast(f"Velkommen {current_player}", icon=":material/waving_hand:")
    st.session_state[WELCOME_TOAST_PLAYER_KEY] = current_player

v.hoved_navbar(["Hjem", "Registrer slag", "Live Runde", "Spiller"], current_player)
selected_page = MAIN_PAGES.get(st.session_state.choosen_mainpage)
if selected_page is not None:
    selected_page()