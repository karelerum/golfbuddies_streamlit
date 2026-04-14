from __future__ import annotations

from pathlib import Path
from typing import Any

import gspread
import google.auth
import streamlit as st
from gspread import Worksheet

from config.settings import get_service_account_file, get_spreadsheet_id


class GoogleSheetsClient:
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self, spreadsheet_id: str | None = None) -> None:
        self.spreadsheet_id = (spreadsheet_id or get_spreadsheet_id()).strip()
        if not self.spreadsheet_id:
            raise ValueError("Mangler spreadsheet_id i .streamlit/secrets.toml")

        self._client = self._build_client()
        self._spreadsheet = self._client.open_by_key(self.spreadsheet_id)

    def _build_client(self) -> gspread.Client:
        service_account_block = st.secrets.get("google_service_account")
        if service_account_block:
            return gspread.service_account_from_dict(dict(service_account_block))

        service_account_file: Path = get_service_account_file()
        if service_account_file.exists():
            return gspread.service_account(filename=str(service_account_file))

        credentials, _ = google.auth.default(scopes=self.SCOPES)
        return gspread.authorize(credentials)

    def get_or_create_worksheet(self, name: str, rows: int = 1000, cols: int = 12) -> Worksheet:
        try:
            return self._spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            return self._spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)

    def get_all_records(self, worksheet_name: str) -> list[dict[str, Any]]:
        ws = self.get_or_create_worksheet(worksheet_name)
        return ws.get_all_records()

    def append_row(self, worksheet_name: str, row_values: list[Any]) -> None:
        ws = self.get_or_create_worksheet(worksheet_name)
        ws.append_row(row_values, value_input_option="USER_ENTERED")

    def get_worksheet_names(self) -> list[str]:
        return [ws.title for ws in self._spreadsheet.worksheets()]
