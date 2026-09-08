import streamlit as st
from config.constants import ADM_PLAYERS

def hoved_navbar(input, innlogget_spiller):
    if "choosen_mainpage" not in st.session_state:
        st.session_state.choosen_mainpage = input[0] if input else "Hjem"
    con = st.container(horizontal= True)
    for side in input:
        con.button(
            side,
            key=f"main_nav_{side}",
            on_click=lambda s=side: st.session_state.update(choosen_mainpage=s),
            type="primary" if st.session_state.choosen_mainpage == side else "secondary",
            use_container_width=True
        )
    if innlogget_spiller in ADM_PLAYERS and "Adm" not in input:
        con.button(
            "Adm",
            key="main_nav_Adm",
            on_click=lambda: st.session_state.update(choosen_mainpage="Adm"),
            type="primary" if st.session_state.choosen_mainpage == "Adm" else "secondary",
            use_container_width=True
        )
    if "Spiller" not in input:
        con.button(
            "Spiller",
            key="main_nav_Spiller",
            on_click=lambda: st.session_state.update(choosen_mainpage="Spiller"),
            type="primary" if st.session_state.choosen_mainpage == "Spiller" else "secondary",
            use_container_width=True
        )

def sub_navbar(input):
    if "choosen_subpage" not in st.session_state:
        st.session_state.choosen_subpage = input[0] if input else "Oversikt"
    con = st.container(horizontal= True)
    for side in input:
        con.button(
            side,
            key=f"sub_nav_{side}",
            on_click=lambda s=side: st.session_state.update(choosen_subpage=s),
            type="primary" if st.session_state.choosen_subpage == side else "secondary",
            use_container_width=True
        )