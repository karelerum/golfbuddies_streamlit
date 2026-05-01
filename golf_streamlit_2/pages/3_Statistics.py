import pandas as pd
import streamlit as st

from config.settings import get_round_spreadsheet_id
from data.google_sheets_client import GoogleSheetsClient
from data.score_repository import ScoreRepository
from utils.auth import get_authenticated_user, require_login

st.set_page_config(page_title="GolfBuddies - Statistikk", page_icon="📊", layout="wide")
st.title("📊 Statistikk")

if not require_login():
    st.stop()

user = get_authenticated_user()

try:
    repo = ScoreRepository(GoogleSheetsClient(spreadsheet_id=get_round_spreadsheet_id()))
    rows = repo.get_scores_for_player(user or "")

    if not rows:
        st.info("Ingen score registrert ennå.")
        st.stop()

    df = pd.DataFrame(rows)
    df["strokes"] = pd.to_numeric(df["strokes"], errors="coerce")
    df["hole_number"] = pd.to_numeric(df["hole_number"], errors="coerce")

    c1, c2, c3 = st.columns(3)
    c1.metric("Rader", len(df))
    c2.metric("Snitt slag", round(float(df["strokes"].mean()), 2))
    c3.metric("Antall runder", int(df["round_id"].nunique()))

    st.subheader("Historikk")
    st.dataframe(df.sort_values(["round_date", "hole_number"]))
except Exception as exc:
    st.error("Klarte ikke hente statistikk fra Google Sheets.")
    st.caption(str(exc))
