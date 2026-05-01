import streamlit as st

from config.settings import get_round_spreadsheet_id
from data.google_sheets_client import GoogleSheetsClient
from data.score_repository import ScoreRepository
from domain.models import ScoreEntry
from utils.auth import get_authenticated_user, require_login

st.set_page_config(page_title="GolfBuddies - Registrer score", page_icon="📝", layout="centered")
st.title("📝 Registrer score")

if not require_login():
    st.stop()

user = get_authenticated_user()

with st.form("score_form", clear_on_submit=True):
    round_id = st.text_input("Runde-ID", value="20260101", help="Format: YYYY + turnering 2 siffer + runde 2 siffer")
    player_list_raw = st.text_input(
        "Spillere i runden (kommaseparert)",
        value=user or "",
        help="Brukes for å opprette spillerkolonner i arket hvis de ikke finnes.",
    )
    hole_number = st.number_input("Hullnummer", min_value=1, max_value=18, value=1, step=1)
    strokes = st.number_input("Slag", min_value=1, max_value=15, value=4, step=1)
    submitted = st.form_submit_button("Lagre score")

if submitted:
    try:
        players = [p.strip() for p in player_list_raw.split(",") if p.strip()]
        if user and user not in players:
            players.append(user)

        client = GoogleSheetsClient(spreadsheet_id=get_round_spreadsheet_id())
        repo = ScoreRepository(client)
        repo.ensure_round_scorecard(round_id=round_id.strip(), players=players)

        score = ScoreEntry(
            round_id=round_id.strip(),
            player=user or "",
            hole_number=int(hole_number),
            strokes=int(strokes),
        )
        repo.add_score(score)
        st.success(f"Score lagret i runde {round_id} (ark i runde_sheets_id).")
    except Exception as exc:
        st.error("Klarte ikke lagre score. Sjekk Google Sheets-oppsett.")
        st.caption(str(exc))
