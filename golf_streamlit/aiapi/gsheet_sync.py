# Alle funksjoner som brukes for å synkronisere data mellom Google Sheets og vårt system.
# Leser og skriver til Google Sheets + oppdaterer sqlite databasen med data fra Google Sheets. Og visa versa

"""
Sync all Google Sheets data to SQLite database
Henter alle tabeller fra Google Sheets og lagrer i SQLite
Sheet names = Table names (direct mapping, no prefixes)
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from aiapi.gsheet import (
    batch_sheets_to_dfs,
    df_to_sheet,
    ensure_gsheet_audit_baseline,
    get_latest_gsheet_audit_timestamp,
    is_internal_worksheet_name,
    list_worksheets,
)
from aiapi.sqlite import get_latest_sqlite_audit_timestamp, get_table_row_count, replace_sqlite_table_from_df, table_exists
from config.constants import SHEETS_LIVE_ROUNDS_URL, SHEETS_MASTER_URL, SHEETS_ROUNDS_URL

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



@dataclass
class SyncIssue:
    level: str
    stage: str
    message: str
    sheet_name: str | None = None

    def to_display_text(self) -> str:
        parts = [self.stage]
        if self.sheet_name:
            parts.append(self.sheet_name)
        prefix = " / ".join(parts)
        return f"{prefix}: {self.message}"


@dataclass
class SyncReport:
    issues: list[SyncIssue] = field(default_factory=list)

    def add_issue(self, level: str, stage: str, message: str, sheet_name: str | None = None) -> None:
        self.issues.append(SyncIssue(level=level, stage=stage, message=message, sheet_name=sheet_name))

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.level == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.level == "warning")

    def extend(self, other: "SyncReport") -> None:
        self.issues.extend(other.issues)

    def status_message(self) -> str:
        if self.ok and self.warning_count == 0:
            return "Synkronisering fullført uten feil."
        if self.ok:
            return f"Synkronisering fullført med {self.warning_count} advarsler."
        if self.warning_count == 0:
            return f"Synkronisering fullført med {self.error_count} feil."
        return f"Synkronisering fullført med {self.error_count} feil og {self.warning_count} advarsler."


def _format_sync_error(exc: Exception) -> str:
    raw_message = str(exc)
    if "Quota exceeded for quota metric 'Read requests'" in raw_message:
        limit_match = re.search(r"limit '([^']+)'", raw_message)
        limit_name = limit_match.group(1) if limit_match else "Read requests per minute per user"
        return (
            f"Google Sheets-kvote overskredet for '{limit_name}'. "
            "For mange lesekall ble sendt pa kort tid. Vent litt og prov igjen."
        )
    return raw_message


def _is_quota_runtime_error(exc: Exception) -> bool:
    raw_message = str(exc)
    return (
        "Google Sheets-kvote truffet" in raw_message
        or "Quota exceeded for quota metric 'Read requests'" in raw_message
        or "[429]" in raw_message
    )


def _get_sheet_url_for_source(source: str) -> tuple[str, str]:
    normalized_source = str(source).strip().lower()
    if normalized_source == "master":
        return SHEETS_MASTER_URL, "master"
    if normalized_source in {"rounds", "runder"}:
        return SHEETS_ROUNDS_URL, "rounds"
    if normalized_source in {"live_rounds", "live-runder", "liverunder"}:
        return SHEETS_LIVE_ROUNDS_URL, "live_rounds"
    raise ValueError("Ugyldig source. Bruk 'master', 'Rounds' eller 'live_rounds'.")


def write_live_round_df_to_gsheet(df: pd.DataFrame, worksheet_name: str) -> SyncReport:
    """Write one live-round table to the dedicated write-only backup spreadsheet."""
    return write_sync_sqlite_to_gsheet_df(df, "live_rounds", worksheet_name)


def _filter_business_worksheets(sheet_names: list[str]) -> list[str]:
    return [sheet_name for sheet_name in sheet_names if not is_internal_worksheet_name(sheet_name)]


def get_latest_gsheet_change_timestamp() -> str | None:
    timestamps = [
        get_latest_gsheet_audit_timestamp(SHEETS_MASTER_URL),
        get_latest_gsheet_audit_timestamp(SHEETS_ROUNDS_URL),
    ]
    existing_timestamps = [timestamp for timestamp in timestamps if timestamp]
    return max(existing_timestamps) if existing_timestamps else None


def sqlite_needs_gsheet_bootstrap() -> bool:
    """Returner True når audit eller minimum lokal state mangler, eller Google Sheets er nyere enn SQLite."""
    latest_sqlite_change = get_latest_sqlite_audit_timestamp()
    if latest_sqlite_change is None:
        return True

    latest_gsheet_change = get_latest_gsheet_change_timestamp()
    if latest_gsheet_change is None:
        return True

    if not table_exists("worksheet_list") or get_table_row_count("worksheet_list") == 0:
        return True

    return latest_gsheet_change > latest_sqlite_change


def ensure_sqlite_seeded_from_gsheet() -> SyncReport:
    """Synk alle Google Sheets til SQLite bare når Google Sheets har nyere audit-endringer."""
    if not sqlite_needs_gsheet_bootstrap():
        return SyncReport()

    logger.info("Google Sheets har nyere data enn SQLite. Starter synkronisering fra Google Sheets.")
    return sync_all_gsheets_to_sqlite()


def write_sync_sqlite_to_gsheet_df(df: pd.DataFrame, source: str, worksheet_name: str | None = None) -> SyncReport:
    """Skrive_sync: synkroniser ett DataFrame fra SQLite/app-state til ett Google Sheet-ark."""
    if df is None:
        raise ValueError("df kan ikke være None.")

    resolved_worksheet_name = worksheet_name or df.attrs.get("worksheet")
    if not resolved_worksheet_name:
        raise ValueError("worksheet_name mangler. Send inn worksheet_name eller sett df.attrs['worksheet'].")

    sheet_url, normalized_source = _get_sheet_url_for_source(source)
    report = SyncReport()

    try:
        df_to_sheet(df, sheet_url, str(resolved_worksheet_name), clear_first=True)
        logger.info(f"Synkroniserte {normalized_source} sheet '{resolved_worksheet_name}' til Google Sheets")
    except Exception as exc:
        logger.error(f"Feil ved synkronisering av {normalized_source} sheet '{resolved_worksheet_name}' til Google Sheets: {exc}")
        report.add_issue("error", f"{normalized_source}/write", _format_sync_error(exc), str(resolved_worksheet_name))

    return report


def sync_df_to_gsheet(df: pd.DataFrame, source: str, worksheet_name: str | None = None) -> SyncReport:
    """Backward-compatible wrapper. Foretrekk write_sync_sqlite_to_gsheet_df()."""
    return write_sync_sqlite_to_gsheet_df(df, source, worksheet_name)


def sync_worksheet_list_to_sqlite() -> SyncReport:
    """Synkroniser liste over alle worksheets til egen tabell"""
    report = SyncReport()
    worksheets_data = []

    try:
        master_sheets = _filter_business_worksheets(list_worksheets(SHEETS_MASTER_URL))
        for sheet_name in master_sheets:
            worksheets_data.append({
                "source": "Master",
                "worksheet": sheet_name,
                "row_count": pd.NA,
                "synced_at": datetime.now().isoformat(),
            })
        logger.info(f"Hentet {len(master_sheets)} master worksheets")
    except Exception as exc:
        logger.error(f"Feil ved henting av master worksheets: {exc}")
        report.add_issue("error", "worksheet_list/master", _format_sync_error(exc))

    try:
        rounds_sheets = _filter_business_worksheets(list_worksheets(SHEETS_ROUNDS_URL))
        for sheet_name in rounds_sheets:
            worksheets_data.append({
                "source": "Rounds",
                "worksheet": sheet_name,
                "row_count": pd.NA,
                "synced_at": datetime.now().isoformat(),
            })
        logger.info(f"Hentet {len(rounds_sheets)} rounds worksheets")
    except Exception as exc:
        logger.error(f"Feil ved henting av rounds worksheets: {exc}")
        report.add_issue("error", "worksheet_list/rounds", _format_sync_error(exc))

    if worksheets_data:
        df = pd.DataFrame(worksheets_data)
        saved = replace_sqlite_table_from_df(df, "worksheet_list")
        if saved:
            logger.info(f"✅ Lagret {len(worksheets_data)} worksheets til 'worksheet_list' tabell")
        else:
            logger.error("Kunne ikke lagre worksheet_list til SQLite")
            report.add_issue("error", "worksheet_list/save", "Kunne ikke lagre worksheet_list til SQLite")
    else:
        logger.warning("Ingen worksheets funnet å lagre")
        report.add_issue("warning", "worksheet_list", "Ingen worksheets funnet å lagre")

    return report


def read_sync_gsheet_to_sqlite_sheet_group(sheet_url: str, sheet_type: str = "") -> SyncReport:
    """Lese_sync: synk alle arker fra en Google Sheets-kilde til SQLite."""
    report = SyncReport()

    try:
        sheet_names = _filter_business_worksheets(list_worksheets(sheet_url))
    except Exception as exc:
        logger.error(f"Feil ved henting av arkfaner {sheet_type}: {exc}")
        report.add_issue("error", f"{sheet_type}/list", _format_sync_error(exc))
        return report

    if not sheet_names:
        return report

    try:
        sheet_dfs = batch_sheets_to_dfs(sheet_url, sheet_names)
    except Exception as exc:
        logger.error(f"Feil ved batch-lesing av {sheet_type} sheets: {exc}")
        report.add_issue("error", f"{sheet_type}/batch_read", _format_sync_error(exc))
        return report

    for sheet_name in sheet_names:
        df = sheet_dfs.get(sheet_name, pd.DataFrame())
        try:
            if not df.empty:
                saved = replace_sqlite_table_from_df(df, sheet_name)
                if not saved:
                    logger.error(f"Kunne ikke lagre {sheet_type} sheet '{sheet_name}' til SQLite")
                    report.add_issue("error", f"{sheet_type}/save", "Kunne ikke lagre til SQLite", sheet_name)
                    continue
                logger.info(f"Synkronisert {sheet_type} sheet '{sheet_name}' til tabell '{sheet_name}'")
            else:
                logger.warning(f"{sheet_type.capitalize()} sheet '{sheet_name}' er tomt")
                report.add_issue("warning", f"{sheet_type}/sheet", "Sheetet er tomt", sheet_name)
        except Exception as exc:
            logger.error(f"Feil ved synking av {sheet_type} sheet '{sheet_name}': {exc}")
            report.add_issue("error", f"{sheet_type}/sheet", _format_sync_error(exc), sheet_name)

    if not report.ok:
        logger.warning(f"{sheet_type.capitalize()} sheets fullførte med feil")
    else:
        logger.info(f"{sheet_type.capitalize()} sheets synkronisert: {len(sheet_names)} sheets")

    return report


def sync_sheets_to_sqlite(sheet_url: str, sheet_type: str = "") -> SyncReport:
    """Backward-compatible wrapper. Foretrekk read_sync_gsheet_to_sqlite_sheet_group()."""
    return read_sync_gsheet_to_sqlite_sheet_group(sheet_url, sheet_type)


def read_sync_gsheet_to_sqlite_master() -> SyncReport:
    """Lese_sync for master-arket."""
    return read_sync_gsheet_to_sqlite_sheet_group(SHEETS_MASTER_URL, "master")


def sync_master_sheets_to_sqlite() -> SyncReport:
    """Backward-compatible wrapper. Foretrekk read_sync_gsheet_to_sqlite_master()."""
    return read_sync_gsheet_to_sqlite_master()


def read_sync_gsheet_to_sqlite_rounds() -> SyncReport:
    """Lese_sync for rounds-arkene."""
    return read_sync_gsheet_to_sqlite_sheet_group(SHEETS_ROUNDS_URL, "rounds")


def sync_rounds_sheets_to_sqlite() -> SyncReport:
    """Backward-compatible wrapper. Foretrekk read_sync_gsheet_to_sqlite_rounds()."""
    return read_sync_gsheet_to_sqlite_rounds()


def read_sync_gsheet_to_sqlite_all() -> SyncReport:
    """Lese_sync: full synk fra Google Sheets til SQLite."""
    combined_report = SyncReport()
    combined_report.extend(sync_worksheet_list_to_sqlite())
    combined_report.extend(sync_master_sheets_to_sqlite())
    combined_report.extend(sync_rounds_sheets_to_sqlite())

    if combined_report.ok:
        for spreadsheet_url, sheet_name in ((SHEETS_MASTER_URL, "master"), (SHEETS_ROUNDS_URL, "rounds")):
            try:
                ensure_gsheet_audit_baseline(spreadsheet_url)
            except RuntimeError as exc:
                if _is_quota_runtime_error(exc):
                    logger.warning(
                        f"Hopper over audit-baseline for {sheet_name} fordi Google Sheets allerede er på kvotegrensen: {exc}"
                    )
                    combined_report.add_issue(
                        "warning",
                        f"audit_baseline/{sheet_name}",
                        "Audit-baseline ble ikke oppdatert fordi Google Sheets allerede er på kvotegrensen.",
                        sheet_name,
                    )
                    continue
                raise
        logger.info("✅ Alle Google Sheets synkronisert til SQLite")
    else:
        logger.warning(combined_report.status_message())

    return combined_report


def sync_all_gsheets_to_sqlite() -> SyncReport:
    """Backward-compatible wrapper. Foretrekk read_sync_gsheet_to_sqlite_all()."""
    return read_sync_gsheet_to_sqlite_all()


if __name__ == "__main__":
    read_sync_gsheet_to_sqlite_all()