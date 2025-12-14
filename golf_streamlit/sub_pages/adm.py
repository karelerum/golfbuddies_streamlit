import pandas as pd
from components.to_from_excel import set_excel, get_excel_w_name
import streamlit as st
import components.psa_tables as p
import components.config as c
import components.functions as f
import components.visuals as v


def page():
    st.set_page_config(page_title="Oppdater Rundeinfo")


    if not st.session_state.get("innlogget_spiller"):
        #f.go_to_page("02_Adm_oppdater_rundeinfo")
        st.write("Gå til Hovedsiden og logg inn")
        st.stop()

    if st.session_state.get("innlogget_spiller") != 'Kåre':
        st.write("Dette er en admin side - prøver du å snoke!?")
        st.stop()

    df = get_excel_w_name("rundeinfo").sort_values("RundeId", ascending=False)
    df["Ferdig_ind"] = df["Ferdig_ind"].astype(bool)
    df["Overfoert_ind"] = df["Overfoert_ind"].astype(bool)
    
    VIS_COLS = [c for c in df.columns if c not in ["TurneringsId", "BaneId"]]

    edited_view = st.data_editor(
        df[VIS_COLS],
        num_rows="dynamic",
        hide_index=True
    )

    df.loc[edited_view.index, VIS_COLS] = edited_view
    edited_df = df

    if st.button("Lagre", type="primary"):
        set_excel("rundeinfo", edited_df)
        st.success("Lagret 👍")

    v.button_update_result()
