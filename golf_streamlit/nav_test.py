import streamlit as st
import components.update_resultat as ur


df = ur.resultat()
st.write(df.head(3))