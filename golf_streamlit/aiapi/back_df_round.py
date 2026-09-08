import pandas as pd

from config.constants import ADM_PLAYERS
from src import my_dfs


ADMIN_PLAYERS = set(ADM_PLAYERS)


def _is_blank_series(series: pd.Series) -> pd.Series:
    normalized_series = series.astype("string")
    stripped_series = normalized_series.str.strip()
    return series.isna() | stripped_series.isin(["", "<NA>", "nan", "None"])


def _is_admin_player(player_name: str | None) -> bool:
    return str(player_name or "") in ADMIN_PLAYERS


def _get_round_info_df() -> pd.DataFrame:
    round_info_df = my_dfs.get_round_info_df()
    if round_info_df is None or round_info_df.empty:
        raise ValueError("Fant ingen data i rundeinfo.")

    required_columns = {"rundeid", "turneringsid", "runde", "bane", "ferdig_ind"}
    missing_columns = required_columns.difference(round_info_df.columns)
    if missing_columns:
        missing_display = ", ".join(sorted(missing_columns))
        raise ValueError(f"rundeinfo mangler kolonner: {missing_display}")

    normalized_df = round_info_df.copy()
    normalized_df["rundeid"] = normalized_df["rundeid"].astype(str)
    normalized_df["turneringsid"] = normalized_df["turneringsid"].astype(str)
    normalized_df["runde"] = pd.to_numeric(normalized_df["runde"], errors="coerce").astype("Int64")
    normalized_df["ferdig_ind"] = pd.to_numeric(normalized_df["ferdig_ind"], errors="coerce").fillna(0).astype(int)
    if "paagaaende_ind" in normalized_df.columns:
        normalized_df["paagaaende_ind"] = pd.to_numeric(normalized_df["paagaaende_ind"], errors="coerce").fillna(0).astype(int)
    else:
        normalized_df["paagaaende_ind"] = 0

    return normalized_df


def _get_tournament_info_df() -> pd.DataFrame:
    tournament_info_df = my_dfs.get_tournament_info_df()
    if tournament_info_df is None or tournament_info_df.empty:
        return pd.DataFrame(columns=["turneringsid", "turneringsnavn"])

    required_columns = {"turneringsid", "turneringsnavn"}
    missing_columns = required_columns.difference(tournament_info_df.columns)
    if missing_columns:
        return pd.DataFrame(columns=["turneringsid", "turneringsnavn"])

    normalized_df = tournament_info_df.copy()
    normalized_df["turneringsid"] = normalized_df["turneringsid"].astype(str)
    normalized_df["turneringsnavn"] = normalized_df["turneringsnavn"].astype(str)
    return normalized_df[["turneringsid", "turneringsnavn"]]


def _get_round_options() -> list[str]:
    if not my_dfs.sqlite_enabled():
        raise ValueError("SQLite er ikke initialisert. Kjor synkronisering for du apner runder.")

    table_list_df = my_dfs.get_table_list()
    if table_list_df is None or table_list_df.empty:
        raise ValueError("Fant ingen data i worksheet_list. Kjor synkronisering for du apner runder.")

    required_columns = {"source", "worksheet"}
    missing_columns = required_columns.difference(table_list_df.columns)
    if missing_columns:
        missing_display = ", ".join(sorted(missing_columns))
        raise ValueError(f"worksheet_list mangler kolonner: {missing_display}")

    rounds_df = table_list_df.loc[
        table_list_df["source"].astype(str).str.lower() == "rounds",
        ["worksheet"],
    ].copy()

    if rounds_df.empty:
        raise ValueError("Fant ingen runder i worksheet_list med kilde 'Rounds'.")

    rounds_df["worksheet"] = rounds_df["worksheet"].astype(str)
    return sorted(rounds_df["worksheet"].unique().tolist(), reverse=True)


def _get_default_round_id(round_options: list[str]) -> str:
    if not round_options:
        raise ValueError("Fant ingen runder å velge mellom.")

    round_info_df = _get_round_info_df()
    available_rounds_df = round_info_df.loc[round_info_df["rundeid"].isin(round_options)].copy()

    open_rounds = sorted(available_rounds_df.loc[available_rounds_df["ferdig_ind"] == 0, "rundeid"].unique().tolist())
    if open_rounds:
        return open_rounds[0]

    finished_rounds = sorted(available_rounds_df["rundeid"].unique().tolist(), reverse=True)
    if finished_rounds:
        return finished_rounds[0]

    return round_options[0]


def _get_round_summary(rundeid) -> dict:
    round_info_df = _get_round_info_df()
    round_row_df = round_info_df.loc[round_info_df["rundeid"] == str(rundeid)]
    if round_row_df.empty:
        raise ValueError(f"Fant ikke rundeinfo for rundeid {rundeid}")

    round_row = round_row_df.iloc[0]
    tournament_name = f"Turnering {round_row['turneringsid']}"
    tournament_info_df = _get_tournament_info_df()
    if not tournament_info_df.empty:
        tournament_row_df = tournament_info_df.loc[tournament_info_df["turneringsid"] == str(round_row["turneringsid"])]
        if not tournament_row_df.empty:
            tournament_name = tournament_row_df.iloc[0]["turneringsnavn"]

    if int(round_row.get("paagaaende_ind", 0)) == 1:
        status = "Pågår"
    elif int(round_row["ferdig_ind"]) == 1:
        status = "Fullført"
    else:
        status = "Åpen"

    return {
        "rundeid": str(round_row["rundeid"]),
        "turneringsid": str(round_row["turneringsid"]),
        "turneringsnavn": tournament_name,
        "runde": int(round_row["runde"]) if pd.notna(round_row["runde"]) else None,
        "bane": str(round_row["bane"]),
        "status": status,
        "ferdig_ind": int(round_row["ferdig_ind"]),
    }


def _update_round_completion_status(round_info_df: pd.DataFrame, rundeid, is_completed: bool) -> pd.DataFrame:
    if round_info_df is None or round_info_df.empty:
        raise ValueError("Fant ingen data i rundeinfo.")

    updated_df = round_info_df.copy()
    if "rundeid" not in updated_df.columns or "ferdig_ind" not in updated_df.columns:
        raise ValueError("rundeinfo mangler kolonnene 'rundeid' og/eller 'ferdig_ind'.")

    row_mask = updated_df["rundeid"].astype(str) == str(rundeid)
    if not row_mask.any():
        raise ValueError(f"Fant ikke rundeinfo for rundeid {rundeid}")

    updated_df.loc[row_mask, "ferdig_ind"] = int(is_completed)
    if "paagaaende_ind" in updated_df.columns:
        updated_df.loc[row_mask, "paagaaende_ind"] = 0

    return updated_df


def _get_visible_player_columns(round_df: pd.DataFrame, player_name: str | None, show_all_players: bool = False) -> list[str]:
    player_columns = sorted([column for column in round_df.columns if column != "hull"])
    if not player_columns:
        raise ValueError("Rundetabellen mangler spillerkolonner.")

    normalized_player_name = str(player_name or "")
    if _is_admin_player(normalized_player_name):
        if show_all_players or normalized_player_name not in player_columns:
            return player_columns
        return [normalized_player_name]

    if normalized_player_name not in player_columns:
        raise ValueError(f"Spiller {normalized_player_name} finnes ikke i valgt runde.")

    return [normalized_player_name]


def _calculate_round_totals(round_df: pd.DataFrame, player_columns: list[str]) -> dict[str, int]:
    totals = {}
    for column in player_columns:
        total_value = pd.to_numeric(round_df[column], errors="coerce").sum(min_count=1)
        totals[column] = 0 if pd.isna(total_value) else int(total_value)
    return totals


def _merge_edited_round_df(base_round_df: pd.DataFrame, edited_round_df: pd.DataFrame) -> pd.DataFrame:
    if "hull" not in base_round_df.columns or "hull" not in edited_round_df.columns:
        raise ValueError("Begge rundetabellene ma inneholde kolonnen 'hull'.")

    missing_columns = [column for column in edited_round_df.columns if column not in base_round_df.columns]
    if missing_columns:
        missing_display = ", ".join(missing_columns)
        raise ValueError(f"Kan ikke lagre ukjente spillerkolonner: {missing_display}")

    merged_df = base_round_df.copy().set_index("hull")
    edited_indexed_df = edited_round_df.copy().set_index("hull")
    merged_df.loc[edited_indexed_df.index, edited_indexed_df.columns] = edited_indexed_df[edited_indexed_df.columns]
    return merged_df.reset_index()


def _get_score_validation_messages(round_df: pd.DataFrame, rundeid, player_columns: list[str]) -> list[str]:
    round_summary = _get_round_summary(rundeid)
    hole_info_df = my_dfs.get_hole_info_df()
    if hole_info_df is None or hole_info_df.empty:
        return []

    required_columns = {"bane", "hull", "par"}
    if required_columns.difference(hole_info_df.columns):
        return []

    par_df = hole_info_df.loc[hole_info_df["bane"] == round_summary["bane"], ["hull", "par"]].copy()
    if par_df.empty:
        return []

    par_df["hull"] = pd.to_numeric(par_df["hull"], errors="coerce").astype("Int64")
    par_df["par"] = pd.to_numeric(par_df["par"], errors="coerce").astype("Int64")
    par_by_hull = {
        int(row["hull"]): int(row["par"])
        for _, row in par_df.dropna(subset=["hull", "par"]).iterrows()
    }

    warning_messages = []
    for _, row in round_df.iterrows():
        hull_value = row.get("hull")
        if pd.isna(hull_value):
            continue

        hull = int(hull_value)
        par_value = par_by_hull.get(hull)
        max_slag = (par_value if par_value is not None else 10) + 6

        for player_column in player_columns:
            score_value = row.get(player_column)
            if pd.isna(score_value):
                continue
            if int(score_value) > max_slag:
                par_display = "?" if par_value is None else str(par_value)
                warning_messages.append(
                    f"Hull {hull}, {player_column}: {int(score_value)} slag er over maks {max_slag} (par {par_display} + 6)"
                )

    return warning_messages


def _prepare_round_df(round_df: pd.DataFrame) -> pd.DataFrame:
    if round_df is None or round_df.empty:
        raise ValueError("Fant ingen data for valgt runde.")

    if "hull" not in round_df.columns:
        raise ValueError("Rundetabellen mangler kolonnen 'hull'.")

    prepared_df = round_df.copy()

    raw_hull = prepared_df["hull"].copy()
    prepared_df.loc[_is_blank_series(raw_hull), "hull"] = pd.NA
    prepared_df["hull"] = pd.to_numeric(prepared_df["hull"], errors="coerce").astype("Int64")
    invalid_hull_mask = ~_is_blank_series(raw_hull) & prepared_df["hull"].isna()
    if invalid_hull_mask.any():
        invalid_values = raw_hull.loc[invalid_hull_mask].astype(str).unique().tolist()
        invalid_display = ", ".join(invalid_values[:5])
        raise ValueError(f"Ugyldige hullverdier i rundetabellen: {invalid_display}")

    player_columns = [column for column in prepared_df.columns if column != "hull"]
    if not player_columns:
        raise ValueError("Rundetabellen mangler spillerkolonner.")

    for column in player_columns:
        raw_values = prepared_df[column].copy()
        prepared_df.loc[_is_blank_series(raw_values), column] = pd.NA
        prepared_df[column] = pd.to_numeric(prepared_df[column], errors="coerce").astype("Int64")
        invalid_value_mask = ~_is_blank_series(raw_values) & prepared_df[column].isna()
        if invalid_value_mask.any():
            invalid_values = raw_values.loc[invalid_value_mask].astype(str).unique().tolist()
            invalid_display = ", ".join(invalid_values[:5])
            raise ValueError(f"Ugyldige slagverdier i kolonnen '{column}': {invalid_display}")

    return prepared_df

def format_round_to_simple_result(round_df: pd.DataFrame, rundeid) -> pd.DataFrame:
    """Konverterer bredt scorekort-format til langt resultat-format."""
    value_columns = [column for column in round_df.columns if column != "hull"]
    result_df = round_df.melt(
        id_vars="hull",
        value_vars=value_columns,
        var_name="spiller",
        value_name="slag",
    )
    result_df.insert(0, "rundeid", rundeid)
    blank_score_mask = _is_blank_series(result_df["slag"])
    result_df.loc[blank_score_mask, "slag"] = pd.NA
    result_df = result_df.dropna(subset=["slag"]).reset_index(drop=True)
    return result_df[["rundeid", "hull", "spiller", "slag"]]