import pandas as pd
from components.to_from_excel import get_excel_w_path, get_excel_w_name
import components.config as c
import components.functions as f
from pathlib import Path
import streamlit as st

def runde(rundeid: int) -> pd.DataFrame:
    filnavn = "runder/" +  f.rundeid_til_filnavn(rundeid)
    return get_excel_w_name(filnavn)

def result_hist() -> pd.DataFrame:
    return get_excel_w_name("resultat_hist")

def turneringsinfo() -> pd.DataFrame:
    return get_excel_w_name("turneringsinfo")

def result_current_raw() -> pd.DataFrame:

    filnavn_liste = [f.name for f in c.RUNDER_DIR.iterdir() if f.is_file()]

    df_total = pd.DataFrame()  # start tom

    dr_rundeinfo = get_excel_w_name("rundeinfo")

    aapne_runder = (
        dr_rundeinfo
        .loc[dr_rundeinfo["Ferdig_ind"] == 0, "RundeId"]
        .unique()
        .astype(str)
    )

    for navn in filnavn_liste:
        stem = Path(navn).stem  # f.eks "Runde_202502_01"
        _, turneringsid, runde = stem.split("_")

        if (turneringsid + runde) in aapne_runder:
            continue
        
        # Les inn fil
        df_part = get_excel_w_path(c.RUNDER_DIR / navn)


        # Melt spillere til rader
        df_part = df_part.melt(
            id_vars=["Hull"],
            var_name="Spiller",
            value_name="Slag"
        )

        # Legg inn metadata
        df_part["TurneringsId"] = str(turneringsid)
        df_part["Runde"] = int(runde)

        # Sett kolonnerekkefølge
        df_part = df_part[["TurneringsId", "Runde", "Hull", "Spiller", "Slag"]]

        # Fjern Slag = NaN (rad-tomme spill)
        df_part = df_part.dropna(subset=["Slag"])

        df_total = df_total._append(df_part, ignore_index = True)

    return df_total

def result_current() -> pd.DataFrame:
    df = result_current_raw()
    # Aggreger til total slag per spiller per runde
   # df = df.groupby([c.TURNERINGSID, c.ROUND, c.SPILLER])[c.VERDI.Slag.value].sum().reset_index()
    df = f.add_6p_syst_col(df)
    df = f.add_1p_syst_col(df)
    df = f.add_beste_slag(df)
    df["AAr"] = df[c.TURNERINGSID].str[:4].astype(int)
    df["RundeId"] = df[c.TURNERINGSID] + df[c.ROUND].astype(str).str.zfill(2)
    df["HullId"] = df["RundeId"] + df["Hull"].astype(str).str.zfill(2)
    df["Par"] = 0  # Placeholder for Par-kolonne
    df["Inne_ind"] = 0  # Placeholder for Inne_ind-kolonne

    return df

st.cache_data
def resultat() -> pd.DataFrame:
    df_hist = result_hist()
    df_current = result_current()
    df = pd.concat([df_hist, df_current], ignore_index=True)
    df["RundeId"] = df["RundeId"].astype(int)
    df[c.TURNERINGSID] = df[c.TURNERINGSID].astype(int)
    dr_rundeinfo = get_excel_w_name("rundeinfo")

    ferdige_runder = (
    dr_rundeinfo
    .loc[dr_rundeinfo["Ferdig_ind"] == 1, "RundeId"]
    .unique()
    )

    df= df[df["RundeId"].isin(ferdige_runder)]

    return df