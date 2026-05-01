import streamlit as st

from utils.auth import is_authenticated, login_form, logout_button


st.set_page_config(page_title="GolfBuddies", page_icon="⛳", layout="wide")
st.title("⛳ GolfBuddies Score App")

st.markdown(
	"""
Denne appen bruker Google Sheets som database.

- Logg inn i sidepanelet.
- Bruk sidene i menyen til venstre for å registrere score og se statistikk.
"""
)

logout_button()

if not is_authenticated():
	login_form()
	st.stop()

st.success("Innlogging OK. Velg en side i menyen til venstre.")
