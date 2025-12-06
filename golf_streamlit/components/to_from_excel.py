import pandas as pd
import streamlit as st
import components.functions as f
from components.config import DATA_DIR


def get_excel_w_name(navn: str) -> pd.DataFrame:
    path = DATA_DIR / f"{navn}.xlsx"
    try:
        return pd.read_excel(path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Excel-fil ikke funnet: {path}")
    except Exception as e:
        raise RuntimeError(f"Feil ved lesing av Excel: {e}")
    
def get_excel_w_path (path: str) -> pd.DataFrame:
    try:
        return pd.read_excel(path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Excel-fil ikke funnet: {path}")
    except Exception as e:
        raise RuntimeError(f"Feil ved lesing av Excel: {e}")
    

def set_runde_excel(rundeid:int, df: pd.DataFrame) -> None:
    filnavn = "runder/" + f.rundeid_til_filnavn(rundeid)
    path = DATA_DIR / f"{filnavn}.xlsx"

    try:
        df.to_excel(path, index=False)
    except PermissionError:
        raise PermissionError(
            f"Kan ikke skrive til filen. Er Excel-filen åpen? {path}"
        )
    except Exception as e:
        raise RuntimeError(f"Feil ved skriving til Excel: {e}")

def set_excel(filnavn:str, df: pd.DataFrame) -> None:
    path = DATA_DIR / f"{filnavn}.xlsx"

    try:
        df.to_excel(path, index=False)
    except PermissionError:
        raise PermissionError(
            f"Kan ikke skrive til filen. Er Excel-filen åpen? {path}"
        )
    except Exception as e:
        raise RuntimeError(f"Feil ved skriving til Excel: {e}")