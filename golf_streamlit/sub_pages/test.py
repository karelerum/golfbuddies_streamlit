import components.update_resultat as r
import streamlit as st

def page():
    df = r.ny_runde()
    st.write(df)