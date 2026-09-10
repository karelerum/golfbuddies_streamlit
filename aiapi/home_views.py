import pandas as pd


def prepare_home_tournaments(
    result_df: pd.DataFrame | None,
    tournament_df: pd.DataFrame | None,
    round_info_df: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if result_df is None or result_df.empty or tournament_df is None or tournament_df.empty or round_info_df is None or round_info_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    normalized_round_info_df = round_info_df.copy()
    normalized_round_info_df["ferdig_ind"] = pd.to_numeric(
        normalized_round_info_df["ferdig_ind"], errors="coerce"
    ).fillna(0).astype(int)

    used_tournament_ids = normalized_round_info_df.loc[
        normalized_round_info_df["rundeid"].astype(str).isin(result_df["rundeid"].astype(str))
        & (normalized_round_info_df["ferdig_ind"] == 1),
        "turneringsid",
    ].astype(str).unique().tolist()

    filtered_tournament_df = tournament_df.loc[
        tournament_df["turneringsid"].astype(str).isin(used_tournament_ids),
        ["turneringsid", "turneringsnavn"],
    ].copy()
    filtered_tournament_df["turneringsid_num"] = pd.to_numeric(filtered_tournament_df["turneringsid"], errors="coerce")
    filtered_tournament_df = filtered_tournament_df.sort_values("turneringsid_num", ascending=False).drop(columns=["turneringsid_num"])

    return filtered_tournament_df, normalized_round_info_df


def get_home_round_options(round_info_df: pd.DataFrame, result_df: pd.DataFrame, tournament_id: str) -> tuple[pd.DataFrame, dict[str, str]]:
    tournament_round_info_df = round_info_df.loc[
        (round_info_df["turneringsid"].astype(str) == str(tournament_id))
        & (round_info_df["ferdig_ind"] == 1)
        & (round_info_df["rundeid"].astype(str).isin(result_df["rundeid"].astype(str))),
        ["runde", "bane"],
    ].copy()
    tournament_round_info_df["runde"] = pd.to_numeric(tournament_round_info_df["runde"], errors="coerce").astype("Int64")
    round_label_map = {
        str(int(row.runde)): f"{row.bane} ({int(row.runde)})" if pd.notna(row.bane) and str(row.bane).strip() else str(int(row.runde))
        for row in tournament_round_info_df.dropna(subset=["runde"]).drop_duplicates(subset=["runde"]).itertuples(index=False)
    }
    return tournament_round_info_df, round_label_map


def build_round_selector_options(tournament_round_info_df: pd.DataFrame, round_label_map: dict[str, str]) -> tuple[list[int], list[str], dict[str, int]]:
    round_options = tournament_round_info_df.dropna(subset=["runde"]).drop_duplicates(subset=["runde"]).sort_values("runde")
    round_option_values = round_options["runde"].astype(int).tolist()
    round_option_labels = [round_label_map.get(str(runde), str(runde)) for runde in round_option_values]
    return round_option_values, round_option_labels, dict(zip(round_option_labels, round_option_values))


def build_home_chart_df(
    result_df: pd.DataFrame,
    round_info_df: pd.DataFrame,
    tournament_id: str,
    valgt_verdi: str,
    value_aliases: dict[str, str],
) -> tuple[pd.DataFrame, str]:
    chart_round_df = round_info_df[["rundeid", "turneringsid", "runde", "ferdig_ind"]].copy()
    chart_round_df["rundeid"] = chart_round_df["rundeid"].astype(str)
    chart_round_df["turneringsid"] = chart_round_df["turneringsid"].astype(str)
    chart_round_df["runde"] = pd.to_numeric(chart_round_df["runde"], errors="coerce").astype("Int64")

    chart_df = result_df.copy()
    chart_df["rundeid"] = chart_df["rundeid"].astype(str)
    chart_df = chart_df.merge(chart_round_df, on="rundeid", how="left")
    value_column = value_aliases.get(valgt_verdi, valgt_verdi)
    chart_df = chart_df.loc[(chart_df["turneringsid"].astype(str) == str(tournament_id)) & (chart_df["ferdig_ind"] == 1)].copy()
    chart_df = chart_df.groupby(["runde", "spiller"], as_index=False)[value_column].sum()
    return chart_df, value_column


def prepare_course_chart_df(course_chart_df: pd.DataFrame, valgt_verdi: str) -> tuple[pd.DataFrame, list[str], list[str] | None, str]:
    prepared_df = course_chart_df.copy()
    prepared_df["stacked_end"] = prepared_df.groupby("spiller", observed=True)["value"].cumsum()
    prepared_df["stacked_start"] = prepared_df["stacked_end"] - prepared_df["value"]
    prepared_df["label_y"] = prepared_df["stacked_start"] + (prepared_df["value"] / 2)
    bane_order = prepared_df[["bane", "bane_order"]].drop_duplicates().sort_values(["bane_order", "bane"])["bane"].tolist()
    player_order = prepared_df["spiller"].cat.categories.tolist() if hasattr(prepared_df["spiller"], "cat") else None
    chart_title = "Poeng" if valgt_verdi == "P6" else valgt_verdi
    return prepared_df, bane_order, player_order, chart_title


def format_numeric_value(value) -> str:
    if pd.isna(value):
        return ""
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"