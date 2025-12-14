import streamlit as st
from time import sleep

PASSORD_MAP = dict(st.secrets["auth"]["passwords"])

def login(spiller: str, passord: str) -> bool:
    if spiller not in PASSORD_MAP:
        return False

    if PASSORD_MAP[spiller] == passord:
        st.session_state["innlogget_spiller"] = spiller
        return True

    return False


def logout():
    st.session_state.pop("innlogget_spiller", None)


def er_innlogget() -> bool:
    return "innlogget_spiller" in st.session_state

def login_med_passord(input_pwd: str) -> str | None:
    for spiller, pwd in PASSORD_MAP.items():
        if pwd == input_pwd:
            st.session_state["innlogget_spiller"] = spiller
            return spiller
    return None

def logg_in_page():
    if not er_innlogget():
        pwd = st.text_input("Passord", type="password")

        if st.button("Logg inn"):
            spiller = login_med_passord(pwd)
            if spiller:
                st.success(f"Innlogget som {spiller}")
                sleep(1.5)
                st.rerun()
            else:
                st.error("Feil passord")
        st.stop()