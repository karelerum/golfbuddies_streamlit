import pandas as pd


PLAYER_VALUE_COLUMNS = {
    "P6": "p6",
    "Slag": "slag",
    "Plass": "plass",
    "Mitt par": "mitt_par",
}

PLAYER_TOURNAMENT_FILTERS = {
    "Bare Sommer": "Sommer",
    "Bare Vinter": "Vinter",
    "Begge": None,
}


def build_player_round_history(
    result_df: pd.DataFrame | None,
    round_info_df: pd.DataFrame | None,
    tournament_df: pd.DataFrame | None,
    player_name: str | None,
) -> pd.DataFrame:
    empty_columns = [
        "rundeid",
        "turneringsid",
        "turneringsnavn",
        "aar",
        "type",
        "runde",
        "bane",
        "p6",
        "slag",
        "plass",
        "par",
        "mitt_par",
        "round_label",
    ]
    if (
        not player_name
        or result_df is None
        or result_df.empty
        or round_info_df is None
        or round_info_df.empty
        or tournament_df is None
        or tournament_df.empty
    ):
        return pd.DataFrame(columns=empty_columns)

    prepared_result_df = result_df.copy()
    prepared_result_df["rundeid"] = prepared_result_df["rundeid"].astype(str)
    prepared_result_df["spiller"] = prepared_result_df["spiller"].astype(str)

    prepared_round_info_df = round_info_df[["rundeid", "turneringsid", "runde", "bane", "ferdig_ind"]].copy()
    prepared_round_info_df["rundeid"] = prepared_round_info_df["rundeid"].astype(str)
    prepared_round_info_df["turneringsid"] = prepared_round_info_df["turneringsid"].astype(str)
    prepared_round_info_df["runde"] = pd.to_numeric(prepared_round_info_df["runde"], errors="coerce").astype("Int64")
    prepared_round_info_df["ferdig_ind"] = pd.to_numeric(prepared_round_info_df["ferdig_ind"], errors="coerce").fillna(0).astype(int)

    prepared_tournament_df = tournament_df[["turneringsid", "turneringsnavn", "aar", "type"]].copy()
    prepared_tournament_df["turneringsid"] = prepared_tournament_df["turneringsid"].astype(str)
    prepared_tournament_df["aar"] = pd.to_numeric(prepared_tournament_df["aar"], errors="coerce").astype("Int64")
    prepared_tournament_df["type"] = prepared_tournament_df["type"].fillna("").astype(str)

    if str(player_name) not in prepared_result_df["spiller"].values:
        return pd.DataFrame(columns=empty_columns)

    merged_df = prepared_result_df.merge(prepared_round_info_df, on="rundeid", how="left")
    merged_df = merged_df.merge(prepared_tournament_df, on="turneringsid", how="left")
    merged_df = merged_df.loc[merged_df["ferdig_ind"] == 1].copy()
    if merged_df.empty:
        return pd.DataFrame(columns=empty_columns)

    round_totals_df = (
        merged_df.groupby(
            ["rundeid", "turneringsid", "turneringsnavn", "aar", "type", "runde", "bane", "spiller"],
            as_index=False,
            dropna=False,
        )[["p6", "slag", "plass", "par"]]
        .sum(min_count=1)
    )

    for column in ["p6", "slag", "plass", "par"]:
        round_totals_df[column] = pd.to_numeric(round_totals_df[column], errors="coerce")

    round_totals_df["plass"] = (
        round_totals_df.groupby("rundeid")["p6"]
        .rank(method="min", ascending=False)
        .astype("Int64")
    )

    grouped_df = round_totals_df.loc[round_totals_df["spiller"] == str(player_name)].copy()
    if grouped_df.empty:
        return pd.DataFrame(columns=empty_columns)

    grouped_df["mitt_par"] = grouped_df["slag"] - grouped_df["par"]

    grouped_df["rundeid_sort"] = pd.to_numeric(grouped_df["rundeid"], errors="coerce")
    grouped_df = grouped_df.sort_values(["rundeid_sort", "rundeid"], ascending=[False, False], na_position="last")
    grouped_df["round_label"] = grouped_df.apply(_format_round_label, axis=1)
    return grouped_df.drop(columns=["rundeid_sort"]).reset_index(drop=True)


def filter_player_round_history(round_history_df: pd.DataFrame, tournament_filter_label: str) -> pd.DataFrame:
    tournament_type = PLAYER_TOURNAMENT_FILTERS.get(tournament_filter_label)
    if tournament_type is None:
        return round_history_df.copy()
    return round_history_df.loc[round_history_df["type"] == tournament_type].reset_index(drop=True)


def filter_player_badges_by_tournament_type(
    badges_df: pd.DataFrame,
    tournament_df: pd.DataFrame | None,
    tournament_filter_label: str,
) -> pd.DataFrame:
    """Filter round and tournament badges by season while retaining total badges."""
    tournament_type = PLAYER_TOURNAMENT_FILTERS.get(tournament_filter_label)
    if tournament_type is None or badges_df.empty:
        return badges_df.copy()

    scope_values = badges_df.get("vinner_innen", pd.Series("", index=badges_df.index)).fillna("").astype(str).str.strip().str.lower()
    is_total_badge = scope_values.isin(["total", "totalt"])
    if tournament_df is None or tournament_df.empty or not {"turneringsid", "type"}.issubset(tournament_df.columns):
        return badges_df.loc[is_total_badge].reset_index(drop=True)

    tournament_types_df = tournament_df[["turneringsid", "type"]].copy()
    tournament_types_df["badge_tournament_id"] = tournament_types_df["turneringsid"].astype(str).str.replace(r"\.0$", "", regex=True)
    tournament_types_df["type"] = tournament_types_df["type"].fillna("").astype(str).str.strip().str.lower()
    tournament_types_df = tournament_types_df.drop_duplicates(subset=["badge_tournament_id"])

    prepared_badges_df = badges_df.copy()
    prepared_badges_df["badge_tournament_id"] = prepared_badges_df["turneringsid"].astype(str).str.replace(r"\.0$", "", regex=True)
    prepared_badges_df = prepared_badges_df.merge(
        tournament_types_df[["badge_tournament_id", "type"]],
        on="badge_tournament_id",
        how="left",
    )
    selected_type = tournament_type.lower()
    return prepared_badges_df.loc[
        is_total_badge.to_numpy() | prepared_badges_df["type"].eq(selected_type)
    ].drop(columns=["badge_tournament_id", "type"]).reset_index(drop=True)


def _format_round_label(row: pd.Series) -> str:
    round_id = str(row.get("rundeid") or "")
    year_value = row.get("aar")
    year_text = ""
    if pd.notna(year_value):
        year_text = str(int(year_value))
    elif len(round_id) >= 4 and round_id[:4].isdigit():
        year_text = round_id[:4]
    course_name = str(row.get("bane") or "").strip()
    tournament_name = str(row.get("turneringsnavn") or "").strip()

    if year_text and course_name:
        return f"{year_text} - {course_name}"
    if course_name:
        return course_name
    if year_text and tournament_name:
        return f"{year_text} - {tournament_name}"
    if tournament_name:
        return tournament_name
    if year_text:
        return year_text
    return round_id


def format_player_value_label(value_name: str, value) -> str:
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        return ""

    if float(numeric_value).is_integer():
        formatted_value = str(int(numeric_value))
    else:
        formatted_value = f"{numeric_value:.1f}"

    if value_name == "P6":
        return f"{formatted_value} P"
    if value_name == "Slag":
        return f"{formatted_value} slag"
    if value_name == "Mitt par":
        return f"+ {formatted_value}" if numeric_value >= 0 else f"- {str(formatted_value).lstrip('-')}"
    return formatted_value