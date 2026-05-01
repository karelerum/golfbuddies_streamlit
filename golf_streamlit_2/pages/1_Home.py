import streamlit as st

from config.settings import get_round_spreadsheet_id
from data.google_sheets_client import GoogleSheetsClient
from data.score_repository import ScoreRepository
from utils.auth import get_authenticated_user, require_login

st.set_page_config(page_title="GolfBuddies - Home", page_icon="⛳", layout="wide")
st.title("⛳ GolfBuddies")

if not require_login():
    st.stop()

user = get_authenticated_user()
st.success(f"Hei {user}! Velkommen tilbake.")

st.markdown("Bruk menyen til venstre for å registrere score eller se statistikk.")

try:
    repo = ScoreRepository(GoogleSheetsClient(spreadsheet_id=get_round_spreadsheet_id()))
    all_scores = repo.get_all_scores()
    my_scores = [row for row in all_scores if row.get("player") == user]

    c1, c2 = st.columns(2)
    c1.metric("Antall registrerte slag (deg)", len(my_scores))
    c2.metric("Antall registrerte slag (alle)", len(all_scores))
except Exception as exc:
    st.info("Google Sheets er ikke klart enda. Legg inn credentials i secrets for full funksjon.")
    st.caption(str(exc))
