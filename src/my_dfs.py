# Mer forretningsnær kode. Ferdigbehandlede tabllet. Tilsvarende gull i medalsjon tanktegang for data-behandling. Dette er en "golden copy" av dataene som er ferdigbehandlet og klar for bruk i applikasjonen.

import pandas as pd

from aiapi.result_views import get_completed_tournament_results
from aiapi.sqlite import get_sqlite_df, get_sqlite_df_with_query, replace_sqlite_table_from_df, table_exists


def sqlite_enabled() -> bool:
    """Sjekk om sqlite er initialisert ved å se om worksheet_list tabellen eksisterer"""
    return table_exists("worksheet_list")
    
def get_table_list():
    """Hent liste over alle tilgjengelige worksheets fra worksheet_list tabellen"""
    if sqlite_enabled():
        df = get_sqlite_df("worksheet_list")
        return df
    else:
        return None

def get_round_df(rundeid):
    """Hent rundetabell der rundeid tilsvarer tabellnavn."""
    return get_sqlite_df_with_query(f'SELECT * FROM "{rundeid}"', strict=True)

def get_table_df(table_name):
    """Hent vilkårlig tabell fra SQLite."""
    return get_sqlite_df(table_name, strict=True)

def save_round_df(rundeid, df):
    """Lagre rundetabell der rundeid tilsvarer tabellnavn."""
    return replace_sqlite_table_from_df(df, str(rundeid), strict=True)

def get_result_df():
    """Hent resultat-tabellen hvis den finnes."""
    if table_exists("resultat"):
        return get_sqlite_df("resultat")
    return None

def get_merker_df():
    """Hent merker-tabellen hvis den finnes."""
    if table_exists("merker"):
        return get_sqlite_df("merker")
    return pd.DataFrame()

def get_spillermerker_df():
    """Hent spillermerker-tabellen hvis den finnes."""
    if table_exists("spillermerker"):
        return get_sqlite_df("spillermerker")
    return pd.DataFrame()

def get_round_info_df():
    """Hent rundeinfo-tabellen."""
    return get_sqlite_df("rundeinfo", strict=True)

def save_round_info_df(df):
    """Lagre rundeinfo-tabellen."""
    return replace_sqlite_table_from_df(df, "rundeinfo", strict=True)

def get_hole_info_df():
    """Hent hullinfo-tabellen."""
    return get_sqlite_df("hullinfo", strict=True)

def get_tournament_info_df():
    """Hent turneringsinfo-tabellen hvis den finnes."""
    if table_exists("turneringsinfo"):
        return get_sqlite_df("turneringsinfo")
    return None

def save_result_df(df):
    """Lagre resultat-tabellen."""
    return replace_sqlite_table_from_df(df, "resultat", strict=True)

def save_spillermerker_df(df):
    """Lagre spillermerker-tabellen."""
    return replace_sqlite_table_from_df(df, "spillermerker", strict=True)

def save_table_df(table_name, df):
    """Lagre vilkårlig tabell til SQLite."""
    return replace_sqlite_table_from_df(df, table_name, strict=True)

RESULT_VALUE_ALIASES = {
    "slag": "slag",
    "p6": "p6",
    "p1": "p1",
    "beste_slag": "beste_slag",
    "antall": "antall",
    "plass": "plass",
    "par": "par",
    "indeks": "indeks",
    "spiller_par": "spiller_par",
    "hole_in_one": "hole_in_one",
    "eagle": "eagle",
    "birdie": "birdie",
    "par_ind": "par_ind",
    "bogey": "bogey",
    "double_bogey": "double_bogey",
    "triple_bogey": "triple_bogey",
    "other_ind": "other_ind",
    "Slag": "slag",
    "P6": "p6",
    "P1": "p1",
    "Beste_slag": "beste_slag",
    "Antall": "antall",
    "Plass": "plass",
    "Par": "par",
    "Indeks": "indeks",
    "Spiller_par": "spiller_par",
    "Hole in one": "hole_in_one",
    "Eagle": "eagle",
    "Birdie": "birdie",
    "Par_ind": "par_ind",
    "Bogey": "bogey",
    "2 Bogey": "double_bogey",
    "3 Bogey": "triple_bogey",
    "Other": "other_ind",
}
def resultat_runde_pivot(turneringsid: int, valgt_verdi: str):
    df = get_completed_tournament_results(get_result_df(), get_round_info_df(), turneringsid)
    if df.empty:
        return pd.DataFrame()

    value_column = RESULT_VALUE_ALIASES.get(valgt_verdi, valgt_verdi)
    grouped_df = df.groupby(["runde", "spiller"], as_index=False)[value_column].sum(min_count=1)
    grouped_df[value_column] = pd.to_numeric(grouped_df[value_column], errors="coerce").round(2)

    pivot_df = grouped_df.pivot(index="spiller", columns="runde", values=value_column)
    pivot_df["Total"] = pivot_df.select_dtypes(include="number").sum(axis=1, min_count=1)
    pivot_df.columns = [str(column) for column in pivot_df.columns]

    sort_ascending = value_column == "slag"
    return pivot_df.sort_values(by="Total", ascending=sort_ascending, na_position="last")


def resultat_bane_stacked(turneringsid, valgt_verdi: str):
    df = get_completed_tournament_results(get_result_df(), get_round_info_df(), turneringsid, extra_round_columns=["bane"])
    if df.empty:
        return pd.DataFrame(columns=["spiller", "bane", "value", "total", "bane_order"])

    value_column = RESULT_VALUE_ALIASES.get(valgt_verdi, valgt_verdi)
    grouped_df = (
        df.groupby(["spiller", "bane"], as_index=False)
        .agg(
            value=(value_column, "sum"),
            bane_order=("runde", "min"),
        )
    )
    grouped_df["value"] = pd.to_numeric(grouped_df["value"], errors="coerce")
    grouped_df = grouped_df.dropna(subset=["value", "bane"])
    if grouped_df.empty:
        return pd.DataFrame(columns=["spiller", "bane", "value", "total", "bane_order"])

    total_df = grouped_df.groupby("spiller", as_index=False)["value"].sum().rename(columns={"value": "total"})
    grouped_df = grouped_df.merge(total_df, on="spiller", how="left")
    sort_ascending = value_column == "slag"
    player_order = total_df.sort_values("total", ascending=sort_ascending)["spiller"].tolist()
    grouped_df["spiller"] = pd.Categorical(grouped_df["spiller"], categories=player_order, ordered=True)
    grouped_df = grouped_df.sort_values(["spiller", "bane_order", "bane"])
    return grouped_df.reset_index(drop=True)

def resultat_pr_hull(turneringsid, valgt_runde:int, valgt_verdi: str):
    df = get_completed_tournament_results(get_result_df(), get_round_info_df(), turneringsid)
    if df.empty:
        return pd.DataFrame().style.format(na_rep="")

    value_column = RESULT_VALUE_ALIASES.get(valgt_verdi, valgt_verdi)
    round_mask = pd.to_numeric(df["runde"], errors="coerce") == int(valgt_runde)
    df = df.loc[round_mask].copy()

    pivot = df.pivot_table(
        index="hull",
        columns="spiller",
        values=value_column,
        aggfunc="first"    # én verdi per hull + spiller
    )

    pivot.index.name = None
    pivot = pivot.loc[:, sorted(pivot.columns, key=lambda value: str(value))]

    # Highlight-funksjon: marker høyeste verdier i hver rad
    def highlight(s):
        numeric_s = pd.to_numeric(s, errors="coerce")
        if numeric_s.isna().all():
            return ["" for _ in s]

        if value_column == "slag":
            selected_value = numeric_s.min()
        else:
            selected_value = numeric_s.max()

        is_value = numeric_s == selected_value
    
        return [
            "font-weight: 700; background-color: rgba(255, 65, 65, 0.20);"
            if v else ""
            for v in is_value
        ]

    # Returnér en styler
    pivot = (
        pivot.style
        .apply(highlight, axis=1)
        .format(lambda value: "" if pd.isna(value) else str(int(value)) if float(value).is_integer() else f"{value:.1f}")
    )
    return pivot


def resultat_annet_goy_eagle_osv(turneringsid, valgt_runde=None):
    df = get_completed_tournament_results(get_result_df(), get_round_info_df(), turneringsid)
    if valgt_runde is not None:
        df = df.loc[pd.to_numeric(df["runde"], errors="coerce") == int(valgt_runde)].copy()
    if df.empty:
        return pd.DataFrame(columns=["spiller"])

    df_pre_sum = df[[
        "spiller",
        "hole_in_one",
        "eagle",
        "birdie",
        "par_ind",
        "bogey",
        "double_bogey",
        "triple_bogey",
        "other_ind"
    ]]
    df_sum = df_pre_sum.groupby("spiller", as_index=False).sum()
    df_sum = df_sum.loc[:, (df_sum != 0).any(axis=0)] #Fjern kolonner som bare inneholder 0
    df_sum = df_sum.rename(columns={
        "spiller": "Spiller",
        "hole_in_one": "Hole in one",
        "eagle": "Eagle",
        "birdie": "Birdie",
        "par_ind": "Par",
        "bogey": "Bogey",
        "double_bogey": "2 Bogey",
        "triple_bogey": "3 Bogey",
        "other_ind": "Other",
    })
    sort_columns = [column for column in ["Birdie", "Par"] if column in df_sum.columns]
    if sort_columns:
        df_sum = df_sum.sort_values(by=sort_columns, ascending=[False] * len(sort_columns))
    df_sum = df_sum.reset_index(drop=True)
    return df_sum

def resultat_goy_gruppen_runde(turneringsid):
    df = get_completed_tournament_results(get_result_df(), get_round_info_df(), turneringsid, extra_round_columns=["bane"])
    if df.empty:
        return pd.DataFrame(columns=["Runde", "Bane", "Gruppens par"])

    per_hole_df = df[["runde", "bane", "hull", "slag", "par"]].copy()
    per_hole_df["slag"] = pd.to_numeric(per_hole_df["slag"], errors="coerce")
    per_hole_df["par"] = pd.to_numeric(per_hole_df["par"], errors="coerce")
    per_hole_df = per_hole_df.dropna(subset=["runde", "hull", "slag", "par"])
    if per_hole_df.empty:
        return pd.DataFrame(columns=["Runde", "Bane", "Gruppens par"])

    per_hole_df = (
        per_hole_df
        .groupby(["runde", "bane", "hull"], as_index=False)
        .agg(
            beste_slag=("slag", "min"),
            par=("par", "first"),
        )
    )
    per_hole_df["beste_par"] = per_hole_df["beste_slag"] - per_hole_df["par"]
    df_sum = (
        per_hole_df
        .groupby(["runde", "bane"], as_index=False, dropna=False)
        .agg(Gruppens_par=("beste_par", "sum"))
    )
    df_sum["Gruppens_par"] = df_sum["Gruppens_par"].apply(_format_relative_par_text)
    df_sum.rename(columns={"runde": "Runde", "bane": "Bane", "Gruppens_par": "Gruppens par"}, inplace=True)


    return df_sum


def _format_relative_par_text(value) -> str:
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        return ""

    if float(numeric_value).is_integer():
        formatted_value = str(int(numeric_value))
    else:
        formatted_value = f"{numeric_value:.1f}"

    if numeric_value < 0:
        return f"- {formatted_value.lstrip('-')}"
    return f"+ {formatted_value}"

def resultat_goy_pall(turneringsid):
    df = get_completed_tournament_results(get_result_df(), get_round_info_df(), turneringsid)
    if df.empty:
        return pd.DataFrame(columns=["spiller"])

    df_plass = (
        df
        .groupby("spiller")["plass"]
        .value_counts()
        .unstack(fill_value=0)
        .rename(columns={
            1: "1.plass",
            2: "2.plass",
            3: "3.plass",
            4: "4.plass",
            5: "5.plass",
            6: "6.plass",
            7: "7.plass",
        })
        .sort_values(
            by=["1.plass", "2.plass"],
            ascending=[False, False]
        )
        .reset_index()
    )
    df_plass = df_plass.rename(columns={"spiller": "Spiller"})
    return df_plass
