import pandas as pd
from components.to_from_excel import set_excel, get_excel_w_name
import streamlit as st
import components.psa_tables as p
import components.config as c
import components.functions as f

st.set_page_config(page_title="Oppdater Rundeinfo")

st.title("Oppdater Rundeinfo")

if not st.session_state.get("innlogget_spiller"):
    #f.go_to_page("02_Adm_oppdater_rundeinfo")
    st.write("Gå til Hovedsiden og logg inn")
    st.stop()

if st.session_state.get("innlogget_spiller") != 'Kåre':
    st.write("Dette er en admin side")
    st.stop()

df = get_excel_w_name("rundeinfo").sort_values("RundeId", ascending=False)

edited_df = st.data_editor(
    df,
    num_rows="dynamic",       # ← gjør at man kan legge til (og slette) rader
    use_container_width=True,
    hide_index=True
)

if st.button("Lagre", type="primary"):
    set_excel("rundeinf", edited_df)
    st.success("Lagret 👍")