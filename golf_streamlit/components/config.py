# config/paths.py
from pathlib import Path
from enum import StrEnum

# BASE_DIR = rotmappen til prosjektet (mappen som inneholder "config", "services", "functions", osv.)
BASE_DIR = Path(__file__).resolve().parent.parent

# Katalog all data ligger
DATA_DIR = BASE_DIR / "data"

ALLE_SLAG_PATH = DATA_DIR / "alle_slag.xlsx"

RESULTAT_PATH = DATA_DIR / "alle_slag_m_poeng.xlsx"

TURINERINGSINFO_PATH = DATA_DIR / "turneringsinfo.xlsx"

# Katalog der alle runde-filene ligger
RUNDER_DIR = DATA_DIR / "runder"

# colors.py
SPILLER_FARGER = {
    "Tore":  "#6D4C41",  # brun
    "OleC":  "#43A047",  # grønn
    "Even":  "#E53935",  # rød
    "OleJ":  "#1E88E5",  # klar blå
    "Doff":  "#FB8C00",  # dyp oransje
    "Kåre":  "#8E24AA",  # lilla
    "Erling":"#00ACC1",  # cyan (ny, skiller seg tydelig)
}


# Kolonnenavn – tilpass hvis dine heter noe annet
COL_SEASON = "Sesong"
COL_ROUND = "Runde"
COL_PLAYER = "Spiller"
COL_POINTS_6 = "6-poeng-syst"
COL_TERN_ID = "6-poeng-syst"
POINTS_6 = '6-poeng-syst'
POINTS_1 = '1-poeng-syst'
SLAG = 'Slag'
SEASON = "Sesong"
ROUND = "Runde"
SPILLER = "Spiller"
TURNERINGSID = "TurneringsId"
RUNDE_ID = "RundeId"

REQUIRED_COLUMNS = {
    COL_SEASON,
    COL_ROUND,
    COL_PLAYER,
    COL_POINTS_6,
}

class VERDI(StrEnum):
    P6 = '6-poeng-syst'
    P1 = '1-poeng-syst'
    Slag = 'Slag'

class Col_Res(StrEnum):
    POINTS_6 = '6-poeng-syst'
    POINTS_1 = '1-poeng-syst'
    SLAG = 'Slag'
    SEASON = "Sesong"
    ROUND = "Runde"
    PLAYER = "Spiller"
    TURNERINGSID = "Turneringsid"
