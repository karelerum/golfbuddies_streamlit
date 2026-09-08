import streamlit as st
from ui.components.visuals import sub_navbar
import ui.pages.spiller_merker as subpage_spiller_merker
import ui.pages.spiller_runder as subpage_spiller_runder


PLAYER_SUBPAGES = {
    "Runder": subpage_spiller_runder.page,
    "Merker": subpage_spiller_merker.page,
}


def page():
    st.title("Spiller")

    if st.session_state.get("choosen_subpage") not in PLAYER_SUBPAGES:
        st.session_state.choosen_subpage = list(PLAYER_SUBPAGES)[0]

    sub_navbar(list(PLAYER_SUBPAGES))
    selected_subpage = PLAYER_SUBPAGES.get(st.session_state.choosen_subpage)
    if selected_subpage is not None:
        selected_subpage()