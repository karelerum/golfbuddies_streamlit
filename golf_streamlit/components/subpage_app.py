import streamlit as st
import components.visuals as v
import components.api_tables as t
import components.functions as f
import components.config as c

def sub_page(turneringsid):
    #Filter
    valgt_verdi = v.filter_verdi()

    #TABELL - Poeng pr runde
    df_runde_pivot = t.resultat_runde_pivot(turneringsid, valgt_verdi)
    st.dataframe(df_runde_pivot)

    #LINE CHART - Poeng pr runde
    akkumulert_ind = st.toggle("Vis akkumulert", value=False)
    st.altair_chart(v.line_chart(turneringsid, valgt_verdi, akkumulert_ind)) 

    #TABELL- Alle runder
    valgt_runde = v.dropdown_runde(turneringsid)
    df = t.resultat_pr_hull(turneringsid, valgt_runde, valgt_verdi)
    st.dataframe(df, height= 690)