"""
Project-wide constants for Golf Streamlit application.
Centralized configuration for database, Google Sheets, and scoring parameters.
"""

from pathlib import Path

# ============================================================================
# Database Configuration
# ============================================================================

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "golf.db"
SCHEMA_PATH = DATA_DIR / "schema.sql"

# Table names
TABLE_TOURNAMENTS = "tournaments"
TABLE_COURSES = "courses"
TABLE_HOLES = "holes"
TABLE_ROUNDS = "rounds"
TABLE_PLAYERS = "players"
TABLE_RESULTS = "results"

# Database connection
DB_TIMEOUT_SECONDS = 5
DB_CHECK_SAME_THREAD = False  # Allow multi-threaded access
DB_FOREIGN_KEYS_ENABLED = True

# ============================================================================
# Google Sheets Configuration
# ============================================================================

# Sheet names (mirrors Excel structure)
SHEET_BANEINFO = "baneinfo"
SHEET_HULLINFO = "hullinfo"
SHEET_RUNDEINFO = "rundeinfo"
SHEET_TURNERINGSINFO = "turneringsinfo"
SHEET_RESULTAT = "resultat"
SHEET_ALLE_SLAG = "alle_slag_historisk"

# Google Sheets API scopes
GSHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Google Sheets URLs - 2 separate spreadsheets
# Master data (tournaments, players, courses, holes)
SHEETS_MASTER_URL = "https://docs.google.com/spreadsheets/d/1CbDSEYuYKSGI66dc0y9bGxqNaU0mghhZcbdVw6Bwnqk/edit?gid=2061806810#gid=2061806810"
# Rounds data (one worksheet per round with results)
SHEETS_ROUNDS_URL = "https://docs.google.com/spreadsheets/d/1xcuzzuPseW8q2Q4HkgwgnoFLemKDt-qdCy2FFnhnwL4/edit?gid=0#gid=0"
# Live round backup (write-only from the application)
SHEETS_LIVE_ROUNDS_URL = "https://docs.google.com/spreadsheets/d/1x_9lLCV8o2x2YnKSESjZzcDSMMowm6-1ObWjetVtegU/edit?gid=0#gid=0"

# Service account authentication paths (checked in order)
SERVICE_ACCOUNT_PATHS = [
    Path(__file__).parent.parent.parent / ".streamlit" / "service_account.json",
    Path.home() / ".streamlit" / "service_account.json",
    Path("/etc/secrets/service_account.json"),
]

# Minimum time between Google Sheets audit-log checks (skip network call if within this window)
GSHEET_CHECK_INTERVAL_HOURS = 24

# ============================================================================
# Auth Constants
# ============================================================================

# How long a "remember me" login token stays valid on a device
REMEMBER_ME_DAYS = 7

# ============================================================================
# Scoring System Constants
# ============================================================================

# P6 System: 6-point ranking (1st=6pts, 2nd=5pts, ..., 6th=1pt)
P6_POINTS = {1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}
P6_PENALTY_THRESHOLD = 6  # Slag >= par+6 → 0 pts

# P1 System: 1-point for winners only (plass=1)
P1_WINNER_POINTS = 1

# Live round types
LIVE_ROUND_TYPE_SLAG = "Slag"
LIVE_ROUND_TYPE_6P = "6P"
LIVE_ROUND_TYPES = [LIVE_ROUND_TYPE_SLAG, LIVE_ROUND_TYPE_6P]

# Penalty threshold (slag >= par + threshold → 0 points)
PENALTY_SLAG_THRESHOLD = 6

# Number of holes (standard golf course)
STANDARD_HOLES = 18

# Maximum players per round
MAX_PLAYERS_PER_ROUND = 5

# ============================================================================
# UI Configuration
# ============================================================================

# Tournament types
TOURNAMENT_TYPE_VINTER = "Vinter"
TOURNAMENT_TYPE_SOMMER = "Sommer"

# Result status indicators
ROUND_OPEN = 0  # ferdig_ind=0: Still accepting scores
ROUND_COMPLETE = 1  # ferdig_ind=1: All scores entered

SYNC_NOT_SYNCED = 0  # overfoert_ind=0: Not synced to Sheets
SYNC_SYNCED = 1  # overfoert_ind=1: Synced to Sheets

# ============================================================================
# Cache Configuration
# ============================================================================

# Default cache TTL (seconds)
CACHE_TTL_ROUNDS = 60
CACHE_TTL_RESULTS = 60
CACHE_TTL_TOURNAMENTS = 300

# ============================================================================
# Application Settings
# ============================================================================

# Admin username (hardcoded for now)
ADMIN_USER = "Kåre"

# Page titles
PAGE_TITLE_HOME = "Hjem"
PAGE_TITLE_SCORE_ENTRY = "Registrer slag"
PAGE_TITLE_ADMIN = "Administrasjon"
PAGE_TITLE_LOGOUT = "Logg ut"

# Adm Players
ADM_PLAYERS = ["Kåre"]