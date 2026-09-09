"""
SQLite Database Connection and Base Functions
Manages connection pooling, schema initialization, and high-level DataFrame operations
"""

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Public API
__all__ = [
    "append_audit_log_entry",
    "db",
    "get_latest_sqlite_audit_timestamp",
    "SQLiteOperationError",
    "get_sqlite_df",
    "get_sqlite_df_with_query",
    "get_table_row_count",
    "is_sqlite_ready_for_app",
    "list_sqlite_tables",
    "replace_sqlite_table_from_df",
    "append_sqlite_table_from_df",
    "cleanup_sqlite_artifact_columns",
    "drop_sqlite_table",
    "delete_rows_by_column_values",
    "table_has_column",
    "delete_from_sqlite_table",
    "table_exists",
    "store_auth_token",
    "get_player_for_token",
    "delete_auth_tokens_for_player",
    "delete_expired_auth_tokens",
    "get_meta",
    "set_meta",
    "update_sqlite_row",
]

# Database location
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "golf.db"
SCHEMA_PATH = DATA_DIR / "schema.sql"
AUDIT_LOG_TABLE = "audit_log"


class SQLiteOperationError(RuntimeError):
    """Raised when a SQLite operation fails with context needed by the UI layer."""


class SQLiteConnection:
    """Manages SQLite connection with connection pooling and transaction support"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize connection pool (lazy)"""
        self._initialized = False
    
    @staticmethod
    def _get_connection() -> sqlite3.Connection:
        """Get or create database connection"""
        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Connect with reasonable defaults
        conn = sqlite3.connect(
            str(DB_PATH),
            timeout=5.0,
            check_same_thread=False,  # Allow use across threads (Streamlit)
            isolation_level=None  # Autocommit mode by default
        )
        conn.row_factory = sqlite3.Row  # Access columns by name
        
        # Enable WAL mode, busy timeout, and foreign keys
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        
        return conn
    
    @contextmanager
    def connection(self):
        """Context manager for database connections"""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            pass  # Don't close; reuse for performance
    
    @contextmanager
    def transaction(self, *, immediate: bool = False):
        """Context manager for explicit transactions"""
        conn = self._get_connection()
        conn.isolation_level = "DEFERRED"
        try:
            conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
        finally:
            conn.isolation_level = None
    
    def initialize_schema(self) -> bool:
        """Create tables from schema.sql if they don't exist"""
        if not SCHEMA_PATH.exists():
            error_msg = (
                f"❌ Schema file not found: {SCHEMA_PATH}\n"
                f"Please create the file with your table definitions. "
                f"Location: {SCHEMA_PATH}"
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            with open(SCHEMA_PATH, "r") as f:
                schema_sql = f.read()
            
            with self.connection() as conn:
                conn.executescript(schema_sql)
            
            # Ensure backward-compat view is created
            with self.connection() as conn:
                conn.execute("""
                    DROP VIEW IF EXISTS results_hist
                """)
                conn.execute("""
                    CREATE VIEW results_hist AS SELECT * FROM results
                """)
            
            logger.info(f"SQLite schema initialized: {DB_PATH}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            return False
    
    def ensure_table_exists(self, table_name: str, create_sql: str) -> bool:
        """Create a table if it doesn't exist (for migrations)"""
        try:
            with self.connection() as conn:
                conn.execute(create_sql)
            logger.info(f"Ensured table {table_name} exists")
            return True
        except Exception as e:
            logger.error(f"Failed to ensure table {table_name}: {e}")
            return False
    
    def ensure_column_exists(self, table_name: str, column_name: str, column_def: str) -> bool:
        """Add column to table if it doesn't exist (for migrations)"""
        try:
            with self.connection() as conn:
                # Check if column exists
                cursor = conn.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in cursor.fetchall()]
                
                if column_name not in columns:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")
                    logger.info(f"Added column {column_name} to {table_name}")
                else:
                    logger.info(f"Column {column_name} already exists in {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to ensure column {column_name}: {e}")
            return False


# Global instance
db = SQLiteConnection()


def _quote_identifier(identifier: str) -> str:
    escaped_identifier = identifier.replace('"', '""')
    return f'"{escaped_identifier}"'


def _drop_artifact_columns(df: pd.DataFrame) -> pd.DataFrame:
    artifact_columns = [column for column in ["index", "level_0"] if column in df.columns]
    if not artifact_columns:
        return df
    return df.drop(columns=artifact_columns)


def _list_user_tables(conn: sqlite3.Connection) -> list[str]:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [row[0] for row in cursor.fetchall()]


def _build_sqlite_error(operation: str, target: str, exc: Exception) -> SQLiteOperationError:
    return SQLiteOperationError(
        f"SQLite-feil under {operation} for {target} i {DB_PATH}: {exc}"
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _ensure_audit_log_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_quote_identifier(AUDIT_LOG_TABLE)} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            changed_at TEXT NOT NULL,
            system TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL,
            row_count INTEGER
        )
        """
    )


def append_audit_log_entry(
    system: str,
    action: str,
    target: str,
    row_count: int | None = None,
    changed_at: str | None = None,
    strict: bool = False,
) -> bool:
    """Legg til audit-rad for en endring i SQLite eller Google Sheets."""
    try:
        with db.connection() as conn:
            _ensure_audit_log_table(conn)
            conn.execute(
                f"""
                INSERT INTO {_quote_identifier(AUDIT_LOG_TABLE)}
                    (changed_at, system, action, target, row_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    changed_at or _utc_now_iso(),
                    str(system),
                    str(action),
                    str(target),
                    None if row_count is None else int(row_count),
                ),
            )
        return True
    except Exception as e:
        _handle_sqlite_error("audit-logg", f"audit '{system}:{action}:{target}'", e, strict=strict)
        return False


def get_latest_sqlite_audit_timestamp() -> str | None:
    """Returner sist registrerte audit-tidspunkt i lokal SQLite."""
    try:
        with db.connection() as conn:
            _ensure_audit_log_table(conn)
            cursor = conn.execute(
                f"SELECT MAX(changed_at) FROM {_quote_identifier(AUDIT_LOG_TABLE)}"
            )
            row = cursor.fetchone()
            return str(row[0]) if row and row[0] else None
    except Exception as e:
        logger.error(f"Error reading latest SQLite audit timestamp: {e}")
        return None


def _handle_sqlite_error(operation: str, target: str, exc: Exception, *, strict: bool) -> None:
    wrapped_error = _build_sqlite_error(operation, target, exc)
    logger.error(str(wrapped_error))
    if strict:
        raise wrapped_error from exc


# ============================================================================
# AUTH TOKENS - "husk meg"-tokens for persistent innlogging
# ============================================================================

AUTH_TOKENS_TABLE = "auth_tokens"


def _ensure_auth_tokens_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_quote_identifier(AUTH_TOKENS_TABLE)} (
            token_hash TEXT PRIMARY KEY,
            player_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )


def store_auth_token(token_hash: str, player_name: str, expires_at: str) -> bool:
    try:
        with db.connection() as conn:
            _ensure_auth_tokens_table(conn)
            conn.execute(
                f"""
                INSERT OR REPLACE INTO {_quote_identifier(AUTH_TOKENS_TABLE)}
                    (token_hash, player_name, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(token_hash), str(player_name), _utc_now_iso(), str(expires_at)),
            )
        return True
    except Exception as e:
        _handle_sqlite_error("lagring", f"auth-token for '{player_name}'", e, strict=False)
        return False


def get_player_for_token(token_hash: str) -> str | None:
    """Returner spillernavn for en gyldig, ikke-utløpt token, ellers None."""
    try:
        with db.connection() as conn:
            _ensure_auth_tokens_table(conn)
            cursor = conn.execute(
                f"SELECT player_name, expires_at FROM {_quote_identifier(AUTH_TOKENS_TABLE)} WHERE token_hash = ?",
                (str(token_hash),),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            player_name, expires_at = row
            if str(expires_at) <= _utc_now_iso():
                return None
            return str(player_name)
    except Exception as e:
        logger.error(f"Error reading auth token: {e}")
        return None


def delete_auth_tokens_for_player(player_name: str) -> bool:
    try:
        with db.connection() as conn:
            _ensure_auth_tokens_table(conn)
            conn.execute(
                f"DELETE FROM {_quote_identifier(AUTH_TOKENS_TABLE)} WHERE player_name = ?",
                (str(player_name),),
            )
        return True
    except Exception as e:
        _handle_sqlite_error("sletting", f"auth-tokens for '{player_name}'", e, strict=False)
        return False


def delete_expired_auth_tokens() -> bool:
    try:
        with db.connection() as conn:
            _ensure_auth_tokens_table(conn)
            conn.execute(
                f"DELETE FROM {_quote_identifier(AUTH_TOKENS_TABLE)} WHERE expires_at <= ?",
                (_utc_now_iso(),),
            )
        return True
    except Exception as e:
        _handle_sqlite_error("sletting", "utløpte auth-tokens", e, strict=False)
        return False


# ============================================================================
# APP META - enkel key/value-tabell for f.eks. "sist sjekket mot Google Sheets"
# ============================================================================

APP_META_TABLE = "app_meta"


def _ensure_app_meta_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_quote_identifier(APP_META_TABLE)} (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )


def get_meta(key: str) -> str | None:
    try:
        with db.connection() as conn:
            _ensure_app_meta_table(conn)
            cursor = conn.execute(
                f"SELECT value FROM {_quote_identifier(APP_META_TABLE)} WHERE key = ?",
                (str(key),),
            )
            row = cursor.fetchone()
            return str(row[0]) if row and row[0] is not None else None
    except Exception as e:
        logger.error(f"Error reading app_meta key '{key}': {e}")
        return None


def set_meta(key: str, value: str) -> bool:
    try:
        with db.connection() as conn:
            _ensure_app_meta_table(conn)
            conn.execute(
                f"INSERT OR REPLACE INTO {_quote_identifier(APP_META_TABLE)} (key, value) VALUES (?, ?)",
                (str(key), str(value)),
            )
        return True
    except Exception as e:
        _handle_sqlite_error("lagring", f"app_meta '{key}'", e, strict=False)
        return False


# ============================================================================
# GET FUNCTIONS - Lesing fra database
# ============================================================================

def get_sqlite_df(
    table_name: str,
    strict: bool = False,
    connection: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """Hent hele tabellen som DataFrame"""
    try:
        if connection is not None:
            query = f"SELECT * FROM {_quote_identifier(table_name)}"
            return pd.read_sql_query(query, connection)
        with db.connection() as conn:
            query = f"SELECT * FROM {_quote_identifier(table_name)}"
            df = pd.read_sql_query(query, conn)
            return df
    except Exception as e:
        _handle_sqlite_error("lesing", f"tabell '{table_name}'", e, strict=strict)
        return pd.DataFrame()


def get_sqlite_df_with_query(query: str, strict: bool = False) -> pd.DataFrame:
    """Kjør custom SQL-query og returner resultatet som DataFrame"""
    try:
        with db.connection() as conn:
            df = pd.read_sql_query(query, conn)
            return df
    except Exception as e:
        _handle_sqlite_error("sporring", f"query '{query}'", e, strict=strict)
        return pd.DataFrame()


def table_exists(table_name: str) -> bool:
    """Sjekk om en tabell eksisterer i databasen"""
    with db.connection() as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None


def get_table_row_count(table_name: str, strict: bool = False) -> int:
    """Returner antall rader i en tabell."""
    try:
        with db.connection() as conn:
            query = f"SELECT COUNT(*) AS row_count FROM {_quote_identifier(table_name)}"
            cursor = conn.execute(query)
            row = cursor.fetchone()
            return int(row[0]) if row is not None else 0
    except Exception as e:
        _handle_sqlite_error("telling", f"tabell '{table_name}'", e, strict=strict)
        return 0


def is_sqlite_ready_for_app() -> bool:
    """Returner True når lokal SQLite har minimum state for vanlig app-drift."""
    try:
        return table_exists("worksheet_list") and get_table_row_count("worksheet_list") > 0
    except Exception as e:
        logger.error(f"Error checking SQLite readiness: {e}")
        return False


def list_sqlite_tables() -> list[str]:
    with db.connection() as conn:
        return _list_user_tables(conn)


def table_has_column(table_name: str, column_name: str) -> bool:
    try:
        with db.connection() as conn:
            cursor = conn.execute(f"PRAGMA table_info({_quote_identifier(table_name)})")
            return any(row[1] == column_name for row in cursor.fetchall())
    except Exception as e:
        logger.error(f"Error checking column {column_name} in {table_name}: {e}")
        return False


# ============================================================================
# WRITE FUNCTIONS - Skriving til database
# ============================================================================

def replace_sqlite_table_from_df(df: pd.DataFrame, table_name: str, strict: bool = False) -> bool:
    """Erstatt hele tabellen med data fra DataFrame"""
    try:
        sanitized_df = _drop_artifact_columns(df)
        with db.connection() as conn:
            sanitized_df.to_sql(table_name, conn, if_exists="replace", index=False)
        if table_name != AUDIT_LOG_TABLE:
            append_audit_log_entry("sqlite", "replace", table_name, row_count=len(sanitized_df), strict=False)
        return True
    except Exception as e:
        _handle_sqlite_error("lagring", f"tabell '{table_name}'", e, strict=strict)
        return False


def update_sqlite_row(
    conn: sqlite3.Connection,
    table_name: str,
    key_column: str,
    key_value,
    values: dict[str, object],
) -> None:
    """Update selected columns on one row using an existing transaction connection."""
    if not values:
        return
    assignments = ", ".join(f"{_quote_identifier(column)} = ?" for column in values)
    query = (
        f"UPDATE {_quote_identifier(table_name)} SET {assignments} "
        f"WHERE {_quote_identifier(key_column)} = ?"
    )
    cursor = conn.execute(query, [*values.values(), key_value])
    if cursor.rowcount != 1:
        raise SQLiteOperationError(
            f"Forventet én rad ved oppdatering av '{table_name}', men fant {cursor.rowcount}."
        )


def append_sqlite_table_from_df(df: pd.DataFrame, table_name: str, strict: bool = False) -> bool:
    """Legg til (append) data fra DataFrame til eksisterende tabell"""
    try:
        sanitized_df = _drop_artifact_columns(df)
        with db.connection() as conn:
            sanitized_df.to_sql(table_name, conn, if_exists="append", index=False)
        if table_name != AUDIT_LOG_TABLE:
            append_audit_log_entry("sqlite", "append", table_name, row_count=len(sanitized_df), strict=False)
        return True
    except Exception as e:
        _handle_sqlite_error("append", f"tabell '{table_name}'", e, strict=strict)
        return False


def cleanup_sqlite_artifact_columns() -> list[str]:
    """Fjern vanlige reset_index-artefakter fra alle bruker-tabeller."""
    cleaned_tables: list[str] = []

    try:
        with db.connection() as conn:
            for table_name in _list_user_tables(conn):
                df = pd.read_sql_query(f"SELECT * FROM {_quote_identifier(table_name)}", conn)
                sanitized_df = _drop_artifact_columns(df)

                if list(sanitized_df.columns) == list(df.columns):
                    continue

                sanitized_df.to_sql(table_name, conn, if_exists="replace", index=False)
                cleaned_tables.append(table_name)

            for table_name in cleaned_tables:
                if table_name != AUDIT_LOG_TABLE:
                    append_audit_log_entry("sqlite", "cleanup", table_name)

        return cleaned_tables
    except Exception as e:
        logger.error(f"Error cleaning SQLite artifact columns: {e}")
        return cleaned_tables


def drop_sqlite_table(table_name: str) -> bool:
    try:
        with db.connection() as conn:
            conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        if table_name != AUDIT_LOG_TABLE:
            append_audit_log_entry("sqlite", "drop", table_name)
        return True
    except Exception as e:
        _handle_sqlite_error("sletting", f"tabell '{table_name}'", e, strict=False)
        return False


def delete_rows_by_column_values(table_name: str, column_name: str, values: list[str]) -> bool:
    if not values:
        return True

    try:
        placeholders = ", ".join(["?"] * len(values))
        with db.connection() as conn:
            conn.execute(
                f"DELETE FROM {_quote_identifier(table_name)} WHERE {_quote_identifier(column_name)} IN ({placeholders})",
                tuple(str(value) for value in values),
            )
        if table_name != AUDIT_LOG_TABLE:
            append_audit_log_entry("sqlite", "delete_rows", table_name, row_count=len(values))
        return True
    except Exception as e:
        _handle_sqlite_error(
            "sletting",
            f"tabell '{table_name}' filtrert pa kolonne '{column_name}'",
            e,
            strict=False,
        )
        return False


def delete_from_sqlite_table(table_name: str, where_clause: str = "") -> bool:
    """Slett rader fra tabell basert på where_clause"""
    try:
        with db.connection() as conn:
            query = f"DELETE FROM {_quote_identifier(table_name)}"
            if where_clause:
                query += f" WHERE {where_clause}"
            conn.execute(query)
        if table_name != AUDIT_LOG_TABLE:
            append_audit_log_entry("sqlite", "delete", table_name)
        return True
    except Exception as e:
        _handle_sqlite_error("sletting", f"tabell '{table_name}'", e, strict=False)
        return False
