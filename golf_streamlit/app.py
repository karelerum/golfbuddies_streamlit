import streamlit as st
import components.functions as f
import components.visuals as v
import sub_pages.hjem as hj
import sub_pages.registrer_score as rs
import sub_pages.adm as adm
import sub_pages.test as test
import components.min_auth as a



# 🔐 Sjekk passord helt øverst
a.logg_in_page()

innlogget_spiller = st.session_state.get("innlogget_spiller")


# Initialiser session state for valgt_side hvis ikke allerede satt
if "valgt_side" not in st.session_state:
    st.session_state.valgt_side = "Hjem"
    st.session_state.valgt_innsikt_sub_side = "Turneringsoversikt"

v.hoved_navbar()
if st.session_state.valgt_side == "Hjem":
    v.sub_navbar()
    st.write(f"# {st.session_state.valgt_side} - {st.session_state.valgt_innsikt_sub_side}")
else: st.title(st.session_state.valgt_side)

if st.session_state.valgt_side == "Hjem":
    if st.session_state.valgt_innsikt_sub_side == "Turneringsoversikt":
        hj.turneringsoversikt()
    elif st.session_state.valgt_innsikt_sub_side == "Annet gøy":
        hj.annet_gøy()
elif st.session_state.valgt_side == "Registrer slag":
    rs.page()
elif st.session_state.valgt_side == "Adm":
    adm.page()
elif st.session_state.valgt_side == "TEST":
    test.page()