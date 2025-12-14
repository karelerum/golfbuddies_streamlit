import streamlit as st
import components.visuals as v
import components.api_tables as t
import components.functions as f
import components.config as c

def turneringsoversikt():

    turneringsid = v.dropdown_turnering()

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

def annet_gøy():
    turneringsid = v.dropdown_turnering()
    visnigner = ["Birdie og sånn", "Gruppen pr runde", "Pall-plasser"]
    valgt_visning = v.generell_filterverdi(visnigner)

    if valgt_visning == visnigner[0]:
        df = t.resultat_annet_goy_eagle_osv(turneringsid)
        v.table_uten_totat(df)
        v.linje_diagram(df, "Spiller")

    if valgt_visning == visnigner[1]:
        df = t.resultat_goy_gruppen_runde(turneringsid)
        v.table_uten_totat(df)

    if valgt_visning == visnigner[2]:
        df = t.resultat_goy_pall(turneringsid)
        v.table_uten_totat(df)
        v.linje_diagram(df, "Spiller")
