import pandas as pd
from components.to_from_excel import set_runde_excel
import streamlit as st
import components.psa_tables as p
import components.config as c
import components.functions as f

st.set_page_config(page_title="Registrer slag")

st.title("Registrer slag")
if st.button("Til Hovedside"):
    st.switch_page("app.py")

if not st.session_state.get("innlogget_spiller"):
    #f.go_to_page("02_Adm_oppdater_rundeinfo")
    st.write("Gå til Hovedsiden og logg inn")
    st.stop()

filnavn_liste = [f.name for f in c.RUNDER_DIR.iterdir() if f.is_file()]

df_empty = pd.DataFrame(columns=[
    "TurneringsId",
    "Runde",
    "Hull",
    "Spiller",
    "Slag"
])

df_rundeinfo= p.get_excel_w_name("rundeinfo")

df_rundeinfo = df_rundeinfo.query("Ferdig_ind == 0")
siste_rundeid = df_rundeinfo["RundeId"].min()
df = p.runde(siste_rundeid)

global_spiller = st.session_state["innlogget_spiller"]
vis_alle = False
visable = ["Hull", str(global_spiller)]
if global_spiller == "Kåre":
    vis_alle = st.toggle("Vis alle", value=False)
    if vis_alle: 
        visable = df.columns.to_list()
    

edited_kol = st.data_editor(
    df[visable],
    disabled=["Hull"],
    column_config={
    "Slag": st.column_config.NumberColumn(
        "Slag",
        min_value=0,
        max_value=20,
        step=1,          # 👈 viktig: kun heltall
        format="%d",     # 👈 viser som int uten desimal
        
        )
    },
    height = 670,
    use_container_width=True,
    hide_index=True
)
if not vis_alle:
    antall_slag = edited_kol[global_spiller].sum()
    st.markdown(
        f"<h3 style='text-align:right;'>{F"Totalt: {antall_slag}"}</h3>",
        unsafe_allow_html=True
    )
for col in visable:
    df[col] = edited_kol[col]

if st.button("Lagre", type="primary"):
    set_runde_excel(siste_rundeid, df)
    st.success("Lagret 👍")