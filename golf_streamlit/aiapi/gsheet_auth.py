"""
Google Sheets authentication helper.

Holds the client bootstrap and spreadsheet-open logic so aiapi.gsheet can stay
focused on worksheet operations.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from functools import lru_cache

import gspread
import streamlit as st
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _load_service_account_info(raw_value) -> dict:
    if isinstance(raw_value, str):
        return json.loads(raw_value)
    return dict(raw_value)


def _annotate_client(client: gspread.Client, auth_source: str, service_account_email: str | None = None) -> gspread.Client:
    client._auth_source = auth_source
    client._service_account_email = service_account_email
    return client


def _build_client_from_creds(creds, auth_source: str, service_account_email: str | None = None) -> gspread.Client:
    client = gspread.authorize(creds)
    logger.info(f"Auth ok via {auth_source} ({service_account_email})")
    return _annotate_client(client, auth_source, service_account_email)


def _build_client_from_secret(raw_value, auth_source: str) -> gspread.Client:
    service_account_info = _load_service_account_info(raw_value)
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    return _build_client_from_creds(creds, auth_source, service_account_info.get("client_email"))


def _build_client_from_file(path: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    return _build_client_from_creds(creds, f"service_account.json:{path}", getattr(creds, "service_account_email", None))


def _build_client_from_gcloud(gcloud_cmd: str) -> gspread.Client:
    import subprocess

    token = subprocess.run(
        [gcloud_cmd, "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
        shell=False,
    ).stdout.strip()
    return _build_client_from_creds(OAuthCredentials(token=token), "gcloud_access_token")


def _try_auth(label: str, builder, errors: list[str]) -> gspread.Client | None:
    try:
        return builder()
    except Exception as exc:
        errors.append(f"{label}: {exc}")
        logger.warning(f"Auth metode {label} feilet: {exc}")
        return None


def _format_missing_auth_error(local_sa_paths: list[str], errors: list[str]) -> FileNotFoundError:
    return FileNotFoundError(
        "Ingen autentisering funnet!\n\n"
        "Løsninger (i prioriteringsrekkefølge):\n"
        "1. Bruk st.secrets['google']['sheets_limited_key'] (anbefalt)\n"
        "2. Legg service account JSON-fil på en av disse stedene:\n"
        + "\n".join(f"   {os.path.normpath(p)}" for p in local_sa_paths)
        + "\n3. Kjør: gcloud auth login --enable-gdrive-access\n\n"
        "Forsøk som feilet:\n"
        + "\n".join(f"- {error}" for error in errors)
    )


@lru_cache(maxsize=1)
def _build_gspread_client() -> gspread.Client:
    local_sa_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", ".streamlit", "service_account.json"),
        os.path.join(os.path.expanduser("~"), ".streamlit", "service_account.json"),
    ]
    errors: list[str] = []

    candidates = [
        (
            "sheets_limited_key",
            lambda: _build_client_from_secret(st.secrets["google"]["sheets_limited_key"], "sheets_limited_key"),
        ),
        (
            "gcp_service_account",
            lambda: _build_client_from_secret(st.secrets["gcp_service_account"], "gcp_service_account"),
        ),
    ]

    for path in local_sa_paths:
        normalized_path = os.path.normpath(path)
        if os.path.isfile(normalized_path):
            candidates.append(
                (
                    f"service_account.json:{normalized_path}",
                    lambda normalized_path=normalized_path: _build_client_from_file(normalized_path),
                )
            )

    gcloud_cmd = shutil.which("gcloud")
    if gcloud_cmd:
        candidates.append(
            (
                "gcloud_access_token",
                lambda: _build_client_from_gcloud(gcloud_cmd),
            )
        )

    for label, builder in candidates:
        client = _try_auth(label, builder, errors)
        if client is not None:
            return client

    raise _format_missing_auth_error(local_sa_paths, errors)


def get_gspread_client() -> gspread.Client:
    return _build_gspread_client()


def extract_sheet_id(spreadsheet_url: str) -> str:
    marker = "/d/"
    if marker not in spreadsheet_url:
        return spreadsheet_url
    tail = spreadsheet_url.split(marker, 1)[1]
    return tail.split("/", 1)[0]