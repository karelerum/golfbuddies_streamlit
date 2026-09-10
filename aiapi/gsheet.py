"""
Google Sheets connection helper.

Local dev:   bruker Application Default Credentials (ADC) via gcloud auth application-default login
Produksjon:  bruker Service Account JSON lagret i st.secrets["gcp_service_account"]

Husk å dele Google Sheet med service account:
    sheets-limited-worker@project-e19c8ea2-84a3-47ed-ae5.iam.gserviceaccount.com
"""

import time
import logging
from functools import lru_cache
from datetime import UTC, datetime
import gspread
from gspread.exceptions import APIError
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from gspread.utils import numericise_all, to_records
import pandas as pd

from aiapi.gsheet_auth import extract_sheet_id, get_gspread_client as _auth_get_gspread_client
from aiapi.sqlite import append_audit_log_entry

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

AUDIT_WORKSHEET_TITLE = "audit_log"
AUDIT_WORKSHEET_HEADERS = ["changed_at", "spreadsheet_id", "spreadsheet_title", "worksheet", "action", "row_count"]
INTERNAL_WORKSHEET_TITLES = {AUDIT_WORKSHEET_TITLE}
_AUDIT_HEADERS_READY: set[str] = set()
DATA_WRITE_AUDIT_ENABLED = False

# ---------------------------------------------------------------------------
# Utilities & Retry-logikk
# ---------------------------------------------------------------------------

def _is_quota_error(exc: Exception) -> bool:
    if not isinstance(exc, APIError):
        return False

    message = str(exc).lower()
    quota_markers = [
        "quota exceeded",
        "resource_exhausted",
        "too many requests",
        "rate limit",
        "read requests per minute per user",
        "429",
    ]
    return any(marker in message for marker in quota_markers)


def _run_gsheet_call(action: str, target: str, func, max_retries: int = 5, backoff_base: float = 2.0):
    """Run a Google Sheets call with quota retry and contextual errors."""
    for attempt in range(max_retries):
        try:
            return func()
        except (PermissionError, SpreadsheetNotFound, WorksheetNotFound, FileNotFoundError):
            raise
        except APIError as exc:
            if _is_quota_error(exc):
                raise RuntimeError(f"Google Sheets-kvote truffet under {action} for {target}: {exc}") from exc
            if attempt < max_retries - 1:
                wait_time = backoff_base ** attempt
                logger.warning(
                    f"Google Sheets API-feil under {action} for {target}. Prøver igjen om {wait_time:.0f}s."
                )
                time.sleep(wait_time)
                continue
            raise RuntimeError(f"Google Sheets API-feil under {action} for {target}: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Uventet feil under {action} for {target}: {exc}") from exc


def _serialize_sheet_value(value) -> str:
    if pd.isna(value):
        return ""

    if isinstance(value, str) and value.strip() in {"", "<NA>", "nan", "None"}:
        return ""

    return str(value)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")

def _df_to_values_list(df: pd.DataFrame) -> list[list]:
    """Konverterer DataFrame til liste av rader med blanke celler for manglende verdier."""
    return [[_serialize_sheet_value(value) for value in row] for row in df.to_numpy(dtype=object)]

def _df_with_headers_to_values_list(df: pd.DataFrame) -> list[list]:
    """Konverterer DataFrame til liste med headers først, så data rows."""
    return [df.columns.tolist()] + _df_to_values_list(df)

def _get_spreadsheet_cache_key(spreadsheet: gspread.Spreadsheet) -> str:
    return extract_sheet_id(spreadsheet.url)


def is_internal_worksheet_name(title: str) -> bool:
    return str(title).strip().lower() in {name.lower() for name in INTERNAL_WORKSHEET_TITLES}


def _ensure_audit_worksheet(spreadsheet: gspread.Spreadsheet) -> gspread.Worksheet:
    try:
        worksheet = _get_worksheet(spreadsheet, AUDIT_WORKSHEET_TITLE)
    except WorksheetNotFound:
        worksheet = _run_gsheet_call(
            "oppretting",
            f"worksheet '{AUDIT_WORKSHEET_TITLE}' i '{spreadsheet.title}'",
            lambda: spreadsheet.add_worksheet(title=AUDIT_WORKSHEET_TITLE, rows=1000, cols=len(AUDIT_WORKSHEET_HEADERS) + 2),
        )
        _cached_get_worksheet.cache_clear()
        _AUDIT_HEADERS_READY.discard(_get_spreadsheet_cache_key(spreadsheet))

    spreadsheet_cache_key = _get_spreadsheet_cache_key(spreadsheet)
    if spreadsheet_cache_key not in _AUDIT_HEADERS_READY:
        header_row = _run_gsheet_call(
            "lesing",
            f"audit-header '{spreadsheet.title}'",
            lambda: worksheet.row_values(1),
        )
        if header_row != AUDIT_WORKSHEET_HEADERS:
            _run_gsheet_call(
                "skriving",
                f"audit-header '{spreadsheet.title}'",
                lambda: worksheet.update([AUDIT_WORKSHEET_HEADERS], "A1:F1"),
            )
        _AUDIT_HEADERS_READY.add(spreadsheet_cache_key)

    return worksheet


def _get_or_create_worksheet(
    spreadsheet: gspread.Spreadsheet,
    worksheet: str | int,
    *,
    rows: int = 1000,
    cols: int = 30,
) -> gspread.Worksheet:
    if isinstance(worksheet, int):
        return _get_worksheet(spreadsheet, worksheet)

    try:
        return _get_worksheet(spreadsheet, worksheet)
    except WorksheetNotFound:
        created_worksheet = _run_gsheet_call(
            "oppretting",
            f"worksheet '{worksheet}' i '{spreadsheet.title}'",
            lambda: spreadsheet.add_worksheet(title=str(worksheet), rows=rows, cols=cols),
        )
        _append_data_write_audit_row(spreadsheet, created_worksheet.title, "create_worksheet")
        _cached_get_worksheet.cache_clear()
        _cached_list_worksheets.cache_clear()
        return created_worksheet


def _append_gsheet_audit_row(
    spreadsheet: gspread.Spreadsheet,
    worksheet_title: str,
    action: str,
    row_count: int | None = None,
) -> None:
    if is_internal_worksheet_name(worksheet_title):
        return

    try:
        changed_at = _utc_now_iso()
        audit_worksheet = _ensure_audit_worksheet(spreadsheet)
        audit_row = [[
            changed_at,
            extract_sheet_id(spreadsheet.url),
            spreadsheet.title,
            str(worksheet_title),
            str(action),
            "" if row_count is None else int(row_count),
        ]]
        _run_gsheet_call(
            "audit-append",
            f"audit-logg '{spreadsheet.title}'",
            lambda: audit_worksheet.append_rows(audit_row),
        )
        append_audit_log_entry(
            "gsheet",
            action,
            f"{spreadsheet.title}/{worksheet_title}",
            row_count=row_count,
            changed_at=changed_at,
            strict=False,
        )
    except Exception as exc:
        logger.warning(f"Klarte ikke å skrive audit-logg for worksheet '{worksheet_title}': {exc}")


def _append_data_write_audit_row(
    spreadsheet: gspread.Spreadsheet,
    worksheet_title: str,
    action: str,
    row_count: int | None = None,
) -> None:
    if not DATA_WRITE_AUDIT_ENABLED:
        return
    _append_gsheet_audit_row(spreadsheet, worksheet_title, action, row_count=row_count)


def ensure_gsheet_audit_baseline(spreadsheet_url: str, action: str = "bootstrap_sync") -> None:
    """Sørg for at audit-loggen finnes og har minst én data-rad."""
    client = get_gspread_client()
    spreadsheet = _open_spreadsheet(client, spreadsheet_url)
    audit_worksheet = _ensure_audit_worksheet(spreadsheet)
    changed_at_values = _run_gsheet_call(
        "lesing",
        f"audit-kolonne '{spreadsheet.title}'",
        lambda: audit_worksheet.col_values(1),
    )
    existing_entries = [value for value in changed_at_values[1:] if str(value).strip()]
    if existing_entries:
        return

    _append_gsheet_audit_row(spreadsheet, "__bootstrap__", action)


def get_latest_gsheet_audit_timestamp(spreadsheet_url: str) -> str | None:
    """Returner sist registrerte audit-tidspunkt i et Google Sheet."""
    client = get_gspread_client()
    spreadsheet = _open_spreadsheet(client, spreadsheet_url)
    try:
        audit_worksheet = spreadsheet.worksheet(AUDIT_WORKSHEET_TITLE)
    except WorksheetNotFound:
        return None

    changed_at_values = _run_gsheet_call(
        "lesing",
        f"audit-kolonne '{spreadsheet.title}'",
        lambda: audit_worksheet.col_values(1),
    )
    timestamps = [str(value) for value in changed_at_values[1:] if str(value).strip()]
    if not timestamps:
        return None

    return timestamps[-1]

# ---------------------------------------------------------------------------
# Autentisering
# ---------------------------------------------------------------------------

def get_gspread_client() -> gspread.Client:
    """
    Returnerer en autorisert gspread-klient (cached).

    Prioriteringsrekkefølge:
    1. st.secrets["google"]["sheets_limited_key"] - Service account JSON (anbefalt)
    2. st.secrets["gcp_service_account"] - Alternativ key location
    3. Local service_account.json filer
    4. gcloud auth login --enable-gdrive-access (gcloud CLI)
    """
    return _auth_get_gspread_client()


@lru_cache(maxsize=32)
def _cached_open_spreadsheet(spreadsheet_url: str) -> gspread.Spreadsheet:
    client = get_gspread_client()
    sheet_id = extract_sheet_id(spreadsheet_url)
    service_account_email = getattr(client, "_service_account_email", None)
    auth_source = getattr(client, "_auth_source", "ukjent")
    try:
        spreadsheet = _run_gsheet_call("åpning", f"regneark {sheet_id}", lambda: client.open_by_url(spreadsheet_url))
        logger.info(f"Spreadsheet åpnet ok: {sheet_id}")
        return spreadsheet
    except PermissionError as exc:
        detail = (
            f"Auth ok via {auth_source}, men kontoen '{service_account_email}' har ikke tilgang til arket {sheet_id}. "
            f"Del arket med denne kontoen og prøv igjen."
        )
        raise PermissionError(detail) from exc
    except SpreadsheetNotFound as exc:
        detail = f"Finner ikke regnearket {sheet_id}. Sjekk at URL-en er korrekt og at kontoen har tilgang."
        raise FileNotFoundError(detail) from exc
    except APIError as exc:
        detail = f"Google Sheets API-feil ved åpning av arket {sheet_id}: {exc}"
        raise RuntimeError(detail) from exc


def _open_spreadsheet(client: gspread.Client, spreadsheet_url: str) -> gspread.Spreadsheet:
    """Open spreadsheet and cache it to avoid repeated API calls."""
    return _cached_open_spreadsheet(spreadsheet_url)


@lru_cache(maxsize=256)
def _cached_get_worksheet(spreadsheet_url: str, worksheet_title: str) -> gspread.Worksheet:
    spreadsheet = _cached_open_spreadsheet(spreadsheet_url)
    worksheet_obj = spreadsheet.worksheet(worksheet_title)
    logger.info(f"Worksheet åpnet ok (cached): {worksheet_title}")
    return worksheet_obj


def _get_worksheet(spreadsheet: gspread.Spreadsheet, worksheet: str | int) -> gspread.Worksheet:
    try:
        if isinstance(worksheet, int):
            worksheet_obj = spreadsheet.get_worksheet(worksheet)
            if worksheet_obj is None:
                raise WorksheetNotFound(f"Worksheet index {worksheet} finnes ikke")
            logger.info(f"Worksheet åpnet ok: index {worksheet}")
            return worksheet_obj
        worksheet_obj = _cached_get_worksheet(spreadsheet.url, str(worksheet))
        logger.info(f"Worksheet åpnet ok: {worksheet}")
        return worksheet_obj
    except WorksheetNotFound as exc:
        raise WorksheetNotFound(f"Finner ikke worksheet '{worksheet}' i regnearket '{spreadsheet.title}'") from exc

# ---------------------------------------------------------------------------
# Les / Skriv – generiske
# ---------------------------------------------------------------------------

def sheet_to_df(spreadsheet_url: str, worksheet: str | int = 0) -> pd.DataFrame:
    """Henter et ark og returnerer det som pandas DataFrame."""
    client = get_gspread_client()
    spreadsheet = _open_spreadsheet(client, spreadsheet_url)
    ws = _get_worksheet(spreadsheet, worksheet)
    records = _run_gsheet_call("lesing", f"worksheet '{ws.title}'", ws.get_all_records)
    return pd.DataFrame(records)


BATCH_READ_CHUNK_SIZE = 15


def _values_to_df(values: list[list[str]]) -> pd.DataFrame:
    """Bygger en DataFrame fra rå ark-verdier, tilsvarende Worksheet.get_all_records()."""
    if not values:
        return pd.DataFrame()

    header_row, *body_rows = values
    width = len(header_row)
    padded_rows = [row + [""] * (width - len(row)) if len(row) < width else row[:width] for row in body_rows]
    numericised_rows = [numericise_all(row) for row in padded_rows]
    return pd.DataFrame(to_records(header_row, numericised_rows))


def batch_sheets_to_dfs(spreadsheet_url: str, worksheet_titles: list[str]) -> dict[str, pd.DataFrame]:
    """Henter flere ark i samme regneark med færrest mulig API-kall (values.batchGet) for å spare lesekvote."""
    if not worksheet_titles:
        return {}

    client = get_gspread_client()
    spreadsheet = _open_spreadsheet(client, spreadsheet_url)
    result: dict[str, pd.DataFrame] = {}

    for chunk_start in range(0, len(worksheet_titles), BATCH_READ_CHUNK_SIZE):
        chunk_titles = worksheet_titles[chunk_start : chunk_start + BATCH_READ_CHUNK_SIZE]
        ranges = [f"'{title}'" for title in chunk_titles]
        response = _run_gsheet_call(
            "batch-lesing",
            f"regneark '{spreadsheet.title}'",
            lambda ranges=ranges: spreadsheet.values_batch_get(ranges),
        )
        value_ranges = response.get("valueRanges", [])
        for title, value_range in zip(chunk_titles, value_ranges):
            result[title] = _values_to_df(value_range.get("values", []))

    return result

def df_to_sheet(
    df: pd.DataFrame,
    spreadsheet_url: str,
    worksheet: str | int = 0,
    clear_first: bool = True,
) -> None:
    """Skriver DataFrame til et ark (overskriver som standard)."""
    client = get_gspread_client()
    spreadsheet = _open_spreadsheet(client, spreadsheet_url)
    ws = _get_or_create_worksheet(
        spreadsheet,
        worksheet,
        rows=max(len(df) + 10, 1000),
        cols=max(len(df.columns) + 5, 30),
    )
    if clear_first:
        _run_gsheet_call("nullstilling", f"worksheet '{ws.title}'", ws.clear)
    _run_gsheet_call(
        "skriving",
        f"worksheet '{ws.title}'",
        lambda: ws.update(_df_with_headers_to_values_list(df)),
    )
    _append_data_write_audit_row(spreadsheet, ws.title, "replace", row_count=len(df))

def append_rows_to_sheet(
    df: pd.DataFrame,
    spreadsheet_url: str,
    worksheet: str | int = 0,
) -> None:
    """Legger til rader nederst i arket uten å slette eksisterende data."""
    client = get_gspread_client()
    spreadsheet = _open_spreadsheet(client, spreadsheet_url)
    ws = _get_worksheet(spreadsheet, worksheet)
    _run_gsheet_call(
        "append",
        f"worksheet '{ws.title}'",
        lambda: ws.append_rows(_df_to_values_list(df)),
    )
    _append_data_write_audit_row(spreadsheet, ws.title, "append", row_count=len(df))

def list_worksheets(spreadsheet_url: str) -> list[str]:
    """Returnerer liste med alle arkfane-navn i et regneark."""
    return list(_cached_list_worksheets(spreadsheet_url))


@lru_cache(maxsize=32)
def _cached_list_worksheets(spreadsheet_url: str) -> tuple[str, ...]:
    spreadsheet = _cached_open_spreadsheet(spreadsheet_url)
    worksheets = _run_gsheet_call("listing", f"regneark '{spreadsheet.title}'", spreadsheet.worksheets)
    return tuple(ws.title for ws in worksheets)

def create_worksheet_if_missing(
    spreadsheet_url: str,
    title: str,
    rows: int = 1000,
    cols: int = 30,
) -> gspread.Worksheet:
    """Oppretter en ny fane hvis den ikke finnes, ellers returnerer eksisterende."""
    client = get_gspread_client()
    spreadsheet = _open_spreadsheet(client, spreadsheet_url)
    worksheet = _get_or_create_worksheet(spreadsheet, title, rows=rows, cols=cols)
    _cached_get_worksheet.cache_clear()
    _cached_list_worksheets.cache_clear()
    return worksheet


def delete_worksheet_if_exists(spreadsheet_url: str, title: str) -> bool:
    client = get_gspread_client()
    spreadsheet = _open_spreadsheet(client, spreadsheet_url)
    try:
        worksheet = _get_worksheet(spreadsheet, title)
    except WorksheetNotFound:
        return False

    _run_gsheet_call(
        "sletting",
        f"worksheet '{title}' i '{spreadsheet.title}'",
        lambda: spreadsheet.del_worksheet(worksheet),
    )
    _append_data_write_audit_row(spreadsheet, title, "delete_worksheet")
    _cached_get_worksheet.cache_clear()
    _cached_list_worksheets.cache_clear()
    return True

def delete_matching_rows(
    spreadsheet_url: str,
    worksheet: str | int,
    col_name: str,
    value,
) -> int:
    """
    Sletter alle rader der kolonne `col_name` == `value`.
    Bruker batch_update for effektivitet.
    Returnerer antall slettede rader.
    """
    client = get_gspread_client()
    spreadsheet = _open_spreadsheet(client, spreadsheet_url)
    ws = _get_worksheet(spreadsheet, worksheet)
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    if df.empty or col_name not in df.columns:
        return 0
    
    mask = df[col_name].astype(str) == str(value)
    rows_to_delete = df.index[mask].tolist()
    
    if not rows_to_delete:
        return 0
    
    # Batch delete: bygg liste med deleteRange requests
    # Sorter omvendt for å slette fra bunn oppover (opprettholder indekser)
    delete_requests = []
    for row_idx in sorted(rows_to_delete, reverse=True):
        # row_idx er 0-basert DataFrame index, sheet row er row_idx + 2 (+1 for header, +1 for 1-basert)
        delete_requests.append({
            "deleteRange": {
                "range": {
                    "sheetId": ws.id,
                    "dimension": "ROWS",
                    "startIndex": row_idx + 1,  # 0-basert sheet index (+1 for header)
                    "endIndex": row_idx + 2,
                }
            }
        })
    
    if delete_requests:
        _run_gsheet_call(
            "batch-sletting",
            f"worksheet '{ws.title}'",
            lambda: spreadsheet.batch_update({"requests": delete_requests}),
        )
        _append_data_write_audit_row(spreadsheet, ws.title, "delete_rows", row_count=len(rows_to_delete))
    
    return len(rows_to_delete)

def upsert_rows(
    df: pd.DataFrame,
    spreadsheet_url: str,
    worksheet: str | int,
    key_col: str,
) -> None:
    """
    Oppdaterer eksisterende rader og legger til nye basert på `key_col`.
    Bruker batch_update for effektivitet (1 API-kall istedenfor N).
    Eksisterende rader med samme nøkkelverdi blir overskrevet.
    """
    client = get_gspread_client()
    spreadsheet = _open_spreadsheet(client, spreadsheet_url)
    ws = _get_worksheet(spreadsheet, worksheet)
    existing = pd.DataFrame(ws.get_all_records())

    if existing.empty:
        _run_gsheet_call(
            "skriving",
            f"worksheet '{ws.title}'",
            lambda: ws.update(_df_with_headers_to_values_list(df)),
        )
        _append_data_write_audit_row(spreadsheet, ws.title, "upsert", row_count=len(df))
        return

    # Separer rader som skal oppdateres fra nye rader
    rows_to_update = {}  # {row_index: new_row_values}
    rows_to_append = []  # [new_row_values]
    
    for _, row in df.iterrows():
        key_val = row[key_col]
        row_values = _df_to_values_list(pd.DataFrame([row]))[0]
        
        # Finn eksisterende rad med samme nøkkel
        matches = existing[existing[key_col].astype(str) == str(key_val)].index.tolist()
        if matches:
            # Oppdater første match
            sheet_row_index = matches[0] + 1  # 0-basert sheet index (skip header)
            rows_to_update[sheet_row_index] = row_values
        else:
            # Ny rad
            rows_to_append.append(row_values)
    
    # Batch update: bygg requests for å oppdatere eksisterende rader
    requests = []
    for sheet_row_index, values in rows_to_update.items():
        requests.append({
            "updateCells": {
                "range": {
                    "sheetId": ws.id,
                    "rowIndex": sheet_row_index,
                    "columnIndex": 0,
                },
                "rows": [{
                    "values": [{"userEnteredValue": {"stringValue": str(v)}} for v in values]
                }],
                "fields": "userEnteredValue",
            }
        })
    
    if requests:
        _run_gsheet_call(
            "batch-oppdatering",
            f"worksheet '{ws.title}'",
            lambda: spreadsheet.batch_update({"requests": requests}),
        )
    
    # Legg til nye rader (kan ikke batch_append, så bruk append_rows)
    if rows_to_append:
        _run_gsheet_call(
            "append",
            f"worksheet '{ws.title}'",
            lambda: ws.append_rows(rows_to_append),
        )

    if requests or rows_to_append:
        _append_data_write_audit_row(spreadsheet, ws.title, "upsert", row_count=len(df))
