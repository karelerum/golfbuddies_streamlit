import pandas as pd 
import components.psa_tables as p
import components.config as c  
from components.to_from_excel import get_runde_rundeid
from components.to_from_excel import get_excel_w_name
from pathlib import Path
import streamlit as st

BASIC_COLUMNS = [
    "AAr","TurneringsId","RundeId","Runde","HullId","Hull","Spiller","Slag"
]

BASIC_COLUMN_TYPES = {
    "AAr": int,
    "TurneringsId": int,
    "RundeId": int,
    "Runde": int,
    "HullId": int,
    "Hull": int,
    "Spiller": str,
    "Slag": int,
}

def sjekk_mot_basic_columns(df: pd.DataFrame) -> pd.DataFrame:
    # 1. Sjekk manglende kolonner
    missing = [col for col in BASIC_COLUMN_TYPES if col not in df.columns]
    if missing:
        raise ValueError(f"Mangler kolonner i DataFrame: {missing}")

    # 2. Behold bare BASIC_COLUMN_TYPES + 3. sorter rekkefølge
    df = df[BASIC_COLUMN_TYPES.keys()].copy()

    # 4. Sett riktige datatyper
    for col, dtype in BASIC_COLUMN_TYPES.items():
        df[col] = df[col].astype(dtype, errors="raise")

    return df

def get_ny_rundeinfo() -> int:
    filnavn_liste = [f.name for f in c.RUNDER_DIR.iterdir() if f.is_file()]

    df_rundeinfo = get_excel_w_name("rundeinfo")

    nye_runde = (
        df_rundeinfo
            .loc[
                (df_rundeinfo["Ferdig_ind"] == 1)
                & (df_rundeinfo["Overfoert_ind"] == 0),
                "RundeId"
            ]
            .unique()
            .astype(str)
    )

    for navn in filnavn_liste:
        stem = Path(navn).stem  # f.eks "Runde_202502_01"
        _, turneringsid, runde = stem.split("_")

        if (turneringsid + runde) in nye_runde:
            return turneringsid, runde
    return 0, 0  # ingen ny runde
            

def ny_runde() -> pd.DataFrame:
    turneringsid, runde = get_ny_rundeinfo()
    if turneringsid == 0 and runde == 0:
        return pd.DataFrame()  # tom df
    
    df = get_runde_rundeid(int(turneringsid + runde))

    # Melt spillere til rader
    df = df.melt(
        id_vars=["Hull"],
        var_name="Spiller",
        value_name="Slag"
    )

    # Legg inn metadata
    df["TurneringsId"] = str(turneringsid)
    df["Runde"] = int(runde)

    # Fjern Slag = NaN (rad-tomme spill)
    df = df.dropna(subset=["Slag"])

    df["AAr"] = df[c.TURNERINGSID].str[:4].astype(int)
    df["RundeId"] = df[c.TURNERINGSID] + df[c.ROUND].astype(str).str.zfill(2)
    df["HullId"] = df["RundeId"] + df["Hull"].astype(str).str.zfill(2)
    df = sjekk_mot_basic_columns(df)

    return df

def add_6p_syst_col(df: pd.DataFrame) -> pd.DataFrame:
    base_points = pd.Series({1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1})

    df["6-poeng-syst"] = [
        base_points.reindex(range(plass, plass + antall), fill_value=0).mean()
        for plass, antall in zip(df["Plass"], df["Antall"])
    ]

    return df

def add_hull_detaljer(df: pd.DataFrame) -> pd.DataFrame:
    df_hull = p.get_hull_detaljer()

    #Legg til på nytt for baner med 9 hull - 1 blir hull 10 osv
    df_baneinfo = p.get_baneinfo()
    df_baneinfo = df_baneinfo[df_baneinfo["AntallHull"] == 9]
    df_ni_hull = df_hull[df_hull["Bane"].isin(df_baneinfo["Bane"])].copy()
    df_ni_hull["Hull"] = df_ni_hull["Hull"].astype(int) + 9


    df_hull = pd.concat([df_hull, df_ni_hull], ignore_index=True)
    df = df.merge(
        df_hull,
        how="left",
        left_on=["RundeId", "Hull"],
        right_on=["RundeId", "Hull"]
    )

    return df

def add_spiller_par(df: pd.DataFrame) -> pd.DataFrame:

    df["Spiller_par"] = df["Slag"].astype(int) - df["Par"].astype(int)
    df["Hole in one"] = (df["Slag"] == 1).astype(bool)

    par_type = ["Eagle", "Birdie", "Par_ind", "Bogey", "2 Bogey", "3 Bogey", "Other"]
    for i, col in enumerate(par_type, start=-2):
        if col == "Other":
            df[col] = (df["Spiller_par"] >= i)
        else: df[col] = (df["Spiller_par"] == i)
    return df

def resultat() -> pd.DataFrame:
        #Hent historikk og ferdig runder -> slå sammen
    df_hist = get_excel_w_name("resultat_hist")
    df_hist = sjekk_mot_basic_columns(df_hist)

    df_ny = ny_runde()

    if not df_ny.empty:
        df = pd.concat([df_hist, df_ny], ignore_index=True)
    else:
        df = df_hist
    
    #Legg til kolonner: 
    df["Beste_slag"] = (
        df.groupby(["TurneringsId", "Runde", "Hull"])["Slag"]
        .transform("min")
    )
    
    df["Antall"] = (
    df.groupby(["HullId", "Slag"])["Slag"]
      .transform("count")
)

    df["Plass"] = (
        df.groupby("HullId")["Slag"]
        .rank(method="min")
        .astype(int)
    )

    df = add_6p_syst_col(df)
    df["1-poeng-syst"] = (
        (df["Plass"] == 1).astype(int) / df["Antall"]
    ).round(2)

    df = add_hull_detaljer(df)
    df = add_spiller_par(df)
    return df

def update_resultat():

    #oppdater historikk fil
    df_current_hist = get_excel_w_name("resultat_hist")

    backup_filbane = c.DATA_DIR / "backup" / f"resultat_hist_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with pd.ExcelWriter(backup_filbane, engine="openpyxl", mode="w") as writer:
        df_current_hist.to_excel(writer, index=False, sheet_name="resultat_hist")

    #Oppdater resultat med nye runde
    df = resultat()
    filbane = c.DATA_DIR / "resultat_hist.xlsx"

    with pd.ExcelWriter(filbane, engine="openpyxl", mode="w") as writer:
        df.to_excel(writer, index=False, sheet_name="resultat_hist")

