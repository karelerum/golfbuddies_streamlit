from pathlib import Path

import streamlit as st


DEFAULT_SCORE_SHEET = "scores"
DEFAULT_PLAYERS_SHEET = "players"


def _get_first_secret(keys: list[str], default: str = "") -> str:
    for key in keys:
        value = st.secrets.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def get_spreadsheet_id() -> str:
    return get_round_spreadsheet_id() or get_general_spreadsheet_id()


def get_round_spreadsheet_id() -> str:
    return _get_first_secret(
        [
            "runde_sheets_id",
            "Runde_Sheets_id",
            "spreadsheet_id",
            "general_sheets_id",
            "General_Sheets_id",
        ]
    )


def get_general_spreadsheet_id() -> str:
    return _get_first_secret(["general_sheets_id", "General_Sheets_id"])


def get_service_account_file() -> Path:
    raw = _get_first_secret(["service_account_file", "service_account_json_path"], ".streamlit/service_account.json")
    return Path(raw)


def get_service_account_email() -> str:
    return _get_first_secret(["service_account_email", "serviceaccount"])


def get_sheets_score_worksheet() -> str:
    name = st.secrets.get("scores_worksheet", DEFAULT_SCORE_SHEET)
    return str(name).strip() or DEFAULT_SCORE_SHEET


def get_sheets_players_worksheet() -> str:
    name = st.secrets.get("players_worksheet", DEFAULT_PLAYERS_SHEET)
    return str(name).strip() or DEFAULT_PLAYERS_SHEET
