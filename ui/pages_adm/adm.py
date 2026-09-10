import streamlit as st
from ui.components.visuals import sub_navbar
import ui.pages_adm.adm_sync as subpage_Adm_sync
import ui.pages_adm.adm_div as subpage_Adm_div
import ui.pages_adm.adm_setup as subpage_Adm_setup
import ui.pages_adm.adm_merker as subpage_Adm_merker
import ui.pages_adm.adm_tournament_setup as subpage_Adm_tournament_setup


ADMIN_SUBPAGES = {
    "Sync": subpage_Adm_sync.page,
    "Turneringsoppsett": subpage_Adm_tournament_setup.page,
    "Merker": subpage_Adm_merker.page,
    "Direkte redigering": subpage_Adm_setup.page,
    "Diverse": subpage_Adm_div.page,
}


def page():
    st.title("Administrasjon")
    sub_navbar(list(ADMIN_SUBPAGES))
    selected_subpage = ADMIN_SUBPAGES.get(st.session_state.choosen_subpage)
    if selected_subpage is not None:
        selected_subpage()