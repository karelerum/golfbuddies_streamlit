from datetime import datetime

import pandas as pd

from aiapi.gsheet import delete_worksheet_if_exists
from aiapi.gsheet_sync import SyncReport, sync_df_to_gsheet, sync_worksheet_list_to_sqlite
from aiapi.round_result import rebuild_result_df
from aiapi.sqlite import delete_rows_by_column_values, drop_sqlite_table, list_sqlite_tables, table_exists, table_has_column
from config.constants import SHEETS_ROUNDS_URL, STANDARD_HOLES
from src import my_dfs


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_player_options() -> list[str]:
    players_df = my_dfs.get_table_df("spillere")
    if players_df is None or players_df.empty:
        return []

    aliases = players_df.get("Kallenavn", pd.Series(index=players_df.index, dtype="object")).fillna("").astype(str).str.strip()
    names = players_df.get("Navn", pd.Series(index=players_df.index, dtype="object")).fillna("").astype(str).str.strip()
    values = aliases.where(aliases != "", names)
    return [value for value in values.tolist() if value]


def get_course_options() -> list[str]:
    courses_df = my_dfs.get_table_df("baneinfo")
    if courses_df is None or courses_df.empty or "bane" not in courses_df.columns:
        return []
    return sorted(courses_df["bane"].dropna().astype(str).unique().tolist())


def get_tournament_list_df() -> pd.DataFrame:
    tournament_df = my_dfs.get_tournament_info_df()
    if tournament_df is None or tournament_df.empty:
        return pd.DataFrame(columns=["turneringsid", "turneringsnavn", "aar", "type"])
    display_df = tournament_df.copy()
    display_df["turneringsid_num"] = pd.to_numeric(display_df["turneringsid"], errors="coerce")
    return display_df.sort_values("turneringsid_num", ascending=False).drop(columns=["turneringsid_num"])


def get_tournament_players(turneringsid) -> list[str]:
    round_info_df = my_dfs.get_round_info_df()
    if round_info_df is None or round_info_df.empty:
        return []

    round_ids = round_info_df.loc[
        round_info_df["turneringsid"].astype(str) == str(turneringsid),
        "rundeid",
    ].dropna().astype(str).tolist()

    players = set()
    for rundeid in round_ids:
        if not table_exists(rundeid):
            continue
        round_df = my_dfs.get_round_df(rundeid)
        players.update(column for column in round_df.columns if column != "hull")

    return sorted(players)


def get_tournament_rounds(turneringsid) -> list[dict[str, str | int | None]]:
    round_info_df = my_dfs.get_round_info_df()
    if round_info_df is None or round_info_df.empty:
        return []

    rounds_df = round_info_df.loc[
        round_info_df["turneringsid"].astype(str) == str(turneringsid),
        ["rundeid", "runde", "bane"],
    ].copy()
    if rounds_df.empty:
        return []

    rounds_df["runde"] = pd.to_numeric(rounds_df["runde"], errors="coerce")
    rounds_df = rounds_df.sort_values(["runde", "rundeid"], na_position="last")
    return rounds_df.to_dict("records")


def get_next_tournament_id(year: int) -> str:
    tournament_df = my_dfs.get_tournament_info_df()
    year_prefix = str(int(year))
    counters = []

    if tournament_df is not None and not tournament_df.empty:
        for value in tournament_df["turneringsid"].dropna().astype(str):
            if value.startswith(year_prefix) and len(value) >= 6 and value[4:6].isdigit():
                counters.append(int(value[4:6]))

    next_counter = (max(counters) + 1) if counters else 1
    return f"{year_prefix}{next_counter:02d}"


def _get_round_hole_count(bane: str) -> int:
    hole_info_df = my_dfs.get_hole_info_df()
    if hole_info_df is not None and not hole_info_df.empty:
        course_holes = hole_info_df.loc[hole_info_df["bane"].astype(str) == str(bane), "hull"]
        hole_count = pd.to_numeric(course_holes, errors="coerce").dropna().nunique()
        if hole_count:
            return int(hole_count)

    course_df = my_dfs.get_table_df("baneinfo")
    if course_df is not None and not course_df.empty:
        match_df = course_df.loc[course_df["bane"].astype(str) == str(bane), "antall_hull"]
        if not match_df.empty:
            hole_count = pd.to_numeric(match_df, errors="coerce").dropna()
            if not hole_count.empty:
                return int(hole_count.iloc[0])

    return STANDARD_HOLES


def _build_round_df(player_names: list[str], bane: str, existing_round_df: pd.DataFrame | None = None) -> pd.DataFrame:
    hole_count = _get_round_hole_count(bane)
    round_df = pd.DataFrame({"hull": list(range(1, hole_count + 1))}).set_index("hull")

    effective_players = list(player_names)
    if existing_round_df is not None and not existing_round_df.empty:
        effective_players = effective_players or [column for column in existing_round_df.columns if column != "hull"]

    for player_name in effective_players:
        round_df[player_name] = pd.NA

    if existing_round_df is not None and not existing_round_df.empty:
        existing_df = existing_round_df.copy()
        existing_df["hull"] = pd.to_numeric(existing_df["hull"], errors="coerce").astype("Int64")
        existing_df = existing_df.dropna(subset=["hull"]).set_index("hull")

        for column in round_df.columns:
            if column in existing_df.columns:
                overlapping_hulls = round_df.index.intersection(existing_df.index)
                round_df.loc[overlapping_hulls, column] = existing_df.loc[overlapping_hulls, column]

    return round_df.reset_index()


def _get_next_round_id(turneringsid: str, existing_round_ids: list[str]) -> str:
    suffixes = []
    for rundeid in existing_round_ids:
        rundeid_str = str(rundeid)
        if rundeid_str.startswith(str(turneringsid)) and len(rundeid_str) >= len(str(turneringsid)) + 2:
            suffix = rundeid_str[len(str(turneringsid)):len(str(turneringsid)) + 2]
            if suffix.isdigit():
                suffixes.append(int(suffix))

    next_suffix = (max(suffixes) + 1) if suffixes else 1
    return f"{turneringsid}{next_suffix:02d}"


def _save_rounds_and_sync(round_info_df: pd.DataFrame, round_tables: dict[str, pd.DataFrame], sync_report: SyncReport) -> None:
    my_dfs.save_round_info_df(round_info_df)
    for rundeid, round_df in round_tables.items():
        my_dfs.save_round_df(rundeid, round_df)

    sync_report.extend(sync_df_to_gsheet(round_info_df, "master", "rundeinfo"))
    for rundeid, round_df in round_tables.items():
        sync_report.extend(sync_df_to_gsheet(round_df, "rounds", rundeid))


def _save_rounds(round_info_df: pd.DataFrame, round_tables: dict[str, pd.DataFrame]) -> None:
    my_dfs.save_round_info_df(round_info_df)
    for rundeid, round_df in round_tables.items():
        my_dfs.save_round_df(rundeid, round_df)


def _normalize_round_items(turneringsid: str, round_items: list[dict]) -> list[dict[str, str]]:
    normalized_items: list[dict[str, str]] = []
    used_round_ids: list[str] = [str(item.get("rundeid")) for item in round_items if item.get("rundeid")]

    for item in round_items:
        bane = str(item.get("bane") or "").strip()
        if not bane:
            continue

        rundeid = item.get("rundeid")
        if rundeid:
            normalized_items.append({"rundeid": str(rundeid), "bane": bane})
            continue

        new_rundeid = _get_next_round_id(turneringsid, used_round_ids)
        used_round_ids.append(new_rundeid)
        normalized_items.append({"rundeid": new_rundeid, "bane": bane})

    return normalized_items


def create_tournament_with_rounds(turneringsnavn: str, turnering_type: str, aar: int, spillere: list[str], baner: list[str]) -> tuple[str, SyncReport]:
    now = _timestamp()
    turneringsid = get_next_tournament_id(aar)

    tournament_df = my_dfs.get_tournament_info_df()
    if tournament_df is None or tournament_df.empty:
        tournament_df = pd.DataFrame(columns=["turneringsid", "turneringsnavn", "aar", "created_at", "updated_at", "type"])

    tournament_df = tournament_df.copy()
    tournament_df = pd.concat(
        [
            tournament_df,
            pd.DataFrame(
                [{
                    "turneringsid": str(turneringsid),
                    "turneringsnavn": str(turneringsnavn),
                    "aar": int(aar),
                    "created_at": now,
                    "updated_at": now,
                    "type": str(turnering_type),
                }]
            ),
        ],
        ignore_index=True,
    )

    round_info_df = my_dfs.get_round_info_df()
    if round_info_df is None or round_info_df.empty:
        round_info_df = pd.DataFrame(columns=["rundeid", "turneringsid", "runde", "bane", "ferdig_ind", "paagaaende_ind", "created_at", "updated_at"])

    new_round_rows = []
    round_tables = {}
    for round_number, bane in enumerate(baner, start=1):
        rundeid = f"{turneringsid}{round_number:02d}"
        new_round_rows.append(
            {
                "rundeid": rundeid,
                "turneringsid": str(turneringsid),
                "runde": round_number,
                "bane": str(bane),
                "ferdig_ind": 0,
                "paagaaende_ind": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
        round_tables[rundeid] = _build_round_df(spillere, str(bane))

    round_info_df = pd.concat([round_info_df.copy(), pd.DataFrame(new_round_rows)], ignore_index=True)

    my_dfs.save_table_df("turneringsinfo", tournament_df)
    my_dfs.save_round_info_df(round_info_df)
    for rundeid, round_df in round_tables.items():
        my_dfs.save_round_df(rundeid, round_df)

    sync_report = SyncReport()
    sync_report.extend(sync_df_to_gsheet(tournament_df, "master", "turneringsinfo"))
    _save_rounds_and_sync(round_info_df, round_tables, sync_report)
    sync_report.extend(sync_worksheet_list_to_sqlite())

    return turneringsid, sync_report


def update_tournament_with_rounds(turneringsid: str, turneringsnavn: str, turnering_type: str, spillere: list[str], round_items: list[dict]) -> SyncReport:
    now = _timestamp()
    tournament_df = my_dfs.get_tournament_info_df().copy()
    round_info_df = my_dfs.get_round_info_df().copy()

    tournament_mask = tournament_df["turneringsid"].astype(str) == str(turneringsid)
    tournament_df.loc[tournament_mask, "turneringsnavn"] = str(turneringsnavn)
    tournament_df.loc[tournament_mask, "type"] = str(turnering_type)
    if "updated_at" in tournament_df.columns:
        tournament_df.loc[tournament_mask, "updated_at"] = now

    existing_rounds_df = round_info_df.loc[round_info_df["turneringsid"].astype(str) == str(turneringsid)].copy()
    other_rounds_df = round_info_df.loc[round_info_df["turneringsid"].astype(str) != str(turneringsid)].copy()
    existing_rounds_by_id = {str(row["rundeid"]): row for _, row in existing_rounds_df.iterrows()}
    normalized_round_items = _normalize_round_items(turneringsid, round_items)

    updated_round_rows = []
    active_round_ids = []
    round_tables = {}
    for round_number, round_item in enumerate(normalized_round_items, start=1):
        rundeid = str(round_item["rundeid"])
        bane = str(round_item["bane"])
        active_round_ids.append(rundeid)
        existing_row = existing_rounds_by_id.get(rundeid)
        created_at = existing_row.get("created_at", now) if existing_row is not None else now
        ferdig_ind = int(existing_row.get("ferdig_ind", 0)) if existing_row is not None else 0
        paagaaende_ind = int(existing_row.get("paagaaende_ind", 0)) if existing_row is not None else 0
        existing_round_df = my_dfs.get_round_df(rundeid) if table_exists(rundeid) else pd.DataFrame()

        updated_round_rows.append(
            {
                "rundeid": rundeid,
                "turneringsid": str(turneringsid),
                "runde": round_number,
                "bane": str(bane),
                "ferdig_ind": ferdig_ind,
                "paagaaende_ind": paagaaende_ind,
                "created_at": created_at,
                "updated_at": now,
            }
        )
        round_tables[rundeid] = _build_round_df(spillere, str(bane), existing_round_df)

    removed_round_ids = [str(rundeid) for rundeid in existing_rounds_df["rundeid"].astype(str).tolist() if str(rundeid) not in active_round_ids]
    round_info_df = pd.concat([other_rounds_df, pd.DataFrame(updated_round_rows)], ignore_index=True)

    my_dfs.save_table_df("turneringsinfo", tournament_df)
    _save_rounds(round_info_df, round_tables)

    for rundeid in removed_round_ids:
        drop_sqlite_table(rundeid)
        delete_worksheet_if_exists(SHEETS_ROUNDS_URL, rundeid)

    result_df = my_dfs.get_result_df()
    if removed_round_ids and result_df is not None and not result_df.empty:
        result_df = result_df.copy()
        filtered_result_df = result_df.loc[~result_df["rundeid"].astype(str).isin(removed_round_ids)].copy()
        my_dfs.save_result_df(filtered_result_df)

    sync_report = SyncReport()
    sync_report.extend(sync_df_to_gsheet(tournament_df, "master", "turneringsinfo"))
    _save_rounds_and_sync(round_info_df, round_tables, sync_report)
    sync_report.extend(sync_worksheet_list_to_sqlite())

    if existing_rounds_df["bane"].astype(str).tolist() != [item["bane"] for item in normalized_round_items] or get_tournament_players(turneringsid) != sorted(spillere):
        _, rebuild_report = rebuild_result_df(sync_to_gsheet=True)
        sync_report.extend(rebuild_report)

    return sync_report


def delete_tournament(turneringsid: str) -> SyncReport:
    tournament_df = my_dfs.get_tournament_info_df()
    round_info_df = my_dfs.get_round_info_df()
    result_df = my_dfs.get_result_df()
    sync_report = SyncReport()

    if tournament_df is None or tournament_df.empty or round_info_df is None or round_info_df.empty:
        sync_report.add_issue("error", "tournament/delete", "Fant ikke nødvendige turneringstabeller.", str(turneringsid))
        return sync_report

    round_ids = round_info_df.loc[
        round_info_df["turneringsid"].astype(str) == str(turneringsid),
        "rundeid",
    ].dropna().astype(str).tolist()

    filtered_tournament_df = tournament_df.loc[tournament_df["turneringsid"].astype(str) != str(turneringsid)].copy()
    filtered_round_info_df = round_info_df.loc[round_info_df["turneringsid"].astype(str) != str(turneringsid)].copy()
    filtered_result_df = None if result_df is None else result_df.loc[~result_df["rundeid"].astype(str).isin(round_ids)].copy()

    my_dfs.save_table_df("turneringsinfo", filtered_tournament_df)
    my_dfs.save_round_info_df(filtered_round_info_df)
    if filtered_result_df is not None:
        my_dfs.save_result_df(filtered_result_df)

    for table_name in list_sqlite_tables():
        if table_name in {"turneringsinfo", "rundeinfo", "resultat"}:
            continue
        if table_name in round_ids:
            drop_sqlite_table(table_name)
            continue
        if table_has_column(table_name, "turneringsid"):
            delete_rows_by_column_values(table_name, "turneringsid", [str(turneringsid)])
        if round_ids and table_has_column(table_name, "rundeid"):
            delete_rows_by_column_values(table_name, "rundeid", round_ids)

    for rundeid in round_ids:
        delete_worksheet_if_exists(SHEETS_ROUNDS_URL, rundeid)

    sync_report.extend(sync_df_to_gsheet(filtered_tournament_df, "master", "turneringsinfo"))
    sync_report.extend(sync_df_to_gsheet(filtered_round_info_df, "master", "rundeinfo"))
    if filtered_result_df is not None:
        sync_report.extend(sync_df_to_gsheet(filtered_result_df, "master", "resultat"))
    sync_report.extend(sync_worksheet_list_to_sqlite())

    return sync_report


def create_round_in_tournament(
    turneringsid: str,
    bane: str,
    spillere: list[str],
    *,
    sync_to_gsheet: bool = True,
) -> str:
    """Append a single new round to an existing tournament (used by 6P live rounds) and return its rundeid."""
    now = _timestamp()
    round_info_df = my_dfs.get_round_info_df()
    if round_info_df is None or round_info_df.empty:
        round_info_df = pd.DataFrame(columns=["rundeid", "turneringsid", "runde", "bane", "ferdig_ind", "paagaaende_ind", "created_at", "updated_at"])

    tournament_rounds_df = round_info_df.loc[round_info_df["turneringsid"].astype(str) == str(turneringsid)]
    existing_round_ids = tournament_rounds_df["rundeid"].astype(str).tolist()
    next_runde_number = int(pd.to_numeric(tournament_rounds_df["runde"], errors="coerce").max() or 0) + 1
    rundeid = _get_next_round_id(turneringsid, existing_round_ids)

    new_row = pd.DataFrame([{
        "rundeid": rundeid,
        "turneringsid": str(turneringsid),
        "runde": next_runde_number,
        "bane": str(bane),
        "ferdig_ind": 0,
        "paagaaende_ind": 0,
        "created_at": now,
        "updated_at": now,
    }])
    updated_round_info_df = pd.concat([round_info_df, new_row], ignore_index=True)
    round_df = _build_round_df(spillere, str(bane))

    my_dfs.save_round_info_df(updated_round_info_df)
    my_dfs.save_round_df(rundeid, round_df)
    if sync_to_gsheet:
        sync_df_to_gsheet(updated_round_info_df, "master", "rundeinfo")
        sync_df_to_gsheet(round_df, "rounds", rundeid)

    return rundeid


def delete_round_from_tournament(rundeid: str, *, sync_to_gsheet: bool = True) -> None:
    """Remove a single, not-yet-finished round from rundeinfo (used to clean up unfinished 6P live rounds)."""
    round_info_df = my_dfs.get_round_info_df()
    if round_info_df is None or round_info_df.empty:
        return

    row_mask = round_info_df["rundeid"].astype(str) == str(rundeid)
    if not row_mask.any():
        return
    if int(pd.to_numeric(round_info_df.loc[row_mask, "ferdig_ind"], errors="coerce").fillna(0).iloc[0]) != 0:
        return

    updated_round_info_df = round_info_df.loc[~row_mask].reset_index(drop=True)
    my_dfs.save_round_info_df(updated_round_info_df)
    drop_sqlite_table(str(rundeid))
    if sync_to_gsheet:
        delete_worksheet_if_exists(SHEETS_ROUNDS_URL, str(rundeid))
        sync_df_to_gsheet(updated_round_info_df, "master", "rundeinfo")