import time
from dataclasses import dataclass

import pandas as pd

from aiapi.gsheet import sheet_to_df
from aiapi.gsheet_sync import SyncReport, sync_all_gsheets_to_sqlite, sync_df_to_gsheet
from aiapi.round_result import rebuild_result_df
from aiapi.sqlite import replace_sqlite_table_from_df
from config.constants import SHEETS_MASTER_URL, SHEETS_ROUNDS_URL
from src import my_dfs


class AdminTaskError(RuntimeError):
    """Raised when an admin task fails before a SyncReport can describe it."""


@dataclass
class AdminTaskResult:
    message: str
    sync_report: SyncReport
    elapsed_seconds: float | None = None
    row_count: int | None = None

    @property
    def ok(self) -> bool:
        return self.sync_report.ok and self.sync_report.warning_count == 0


def run_full_sync_task() -> AdminTaskResult:
    start = time.time()
    try:
        sync_report = sync_all_gsheets_to_sqlite()
    except Exception as exc:
        raise AdminTaskError(f"Klarte ikke å hente alt fra Google Sheets: {exc}") from exc

    return AdminTaskResult(
        message=sync_report.status_message(),
        sync_report=sync_report,
        elapsed_seconds=time.time() - start,
    )


def run_single_table_sync_task(source: str, worksheet_name: str) -> AdminTaskResult:
    start = time.time()
    normalized_source = str(source).strip().lower()
    if normalized_source == "master":
        sheet_url = SHEETS_MASTER_URL
    elif normalized_source in {"rounds", "runder"}:
        sheet_url = SHEETS_ROUNDS_URL
    else:
        raise AdminTaskError(f"Ugyldig source '{source}'. Bruk 'Master' eller 'Rounds'.")

    sync_report = SyncReport()
    try:
        df = sheet_to_df(sheet_url, worksheet_name)
        saved = replace_sqlite_table_from_df(df, worksheet_name)
        if not saved:
            sync_report.add_issue(
                "error",
                "single_sheet/save",
                "Kunne ikke lagre tabellen til SQLite.",
                worksheet_name,
            )
    except Exception as exc:
        raise AdminTaskError(f"Klarte ikke å hente tabell '{worksheet_name}' fra Google Sheets: {exc}") from exc

    if sync_report.ok:
        message = f"Hentet og lagret tabell '{worksheet_name}' fra {source}."
    else:
        message = f"Hentet tabell '{worksheet_name}', men lagring ga feilmelding."

    return AdminTaskResult(
        message=message,
        sync_report=sync_report,
        elapsed_seconds=time.time() - start,
        row_count=len(df),
    )


def rebuild_result_task() -> AdminTaskResult:
    try:
        result_df, sync_report = rebuild_result_df(sync_to_gsheet=True)
    except Exception as exc:
        raise AdminTaskError(f"Klarte ikke å rekalkulere resultat: {exc}") from exc

    return AdminTaskResult(
        message=f"Rekalkulerte resultat ({len(result_df)} rader) og synkroniserte til Google Sheets.",
        sync_report=sync_report,
        row_count=len(result_df),
    )


def save_master_tables_task(edited_tables: dict[str, pd.DataFrame]) -> AdminTaskResult:
    sync_report = SyncReport()
    try:
        for table_name, edited_df in edited_tables.items():
            my_dfs.save_table_df(table_name, edited_df)
            sync_report.extend(sync_df_to_gsheet(edited_df, "master", table_name))
    except Exception as exc:
        raise AdminTaskError(f"Klarte ikke å lagre master-tabeller: {exc}") from exc

    message = "Lagret og synkroniserte alle master-tabeller."
    if not sync_report.ok or sync_report.warning_count > 0:
        message = "Lagret alle tabeller, men én eller flere synkroniseringer fikk meldinger."

    return AdminTaskResult(message=message, sync_report=sync_report)