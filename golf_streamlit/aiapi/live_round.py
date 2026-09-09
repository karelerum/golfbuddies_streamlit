from datetime import datetime
import json
import logging

import pandas as pd

from aiapi.df_general_cached import clear_cached_df, get_cached_df, set_cached_df
from aiapi.calc_live_to_round import calculate_live_round_df
from aiapi.calc_result_columns import recalculate_6points, recalculate_placement
from aiapi.round_result import get_tournament_p6_totals
from aiapi.round_save import RoundSaveError, save_round_and_sync
from aiapi.sqlite import db, get_sqlite_df, table_exists, update_sqlite_row
from aiapi.tournament_setup import create_round_in_tournament, delete_round_from_tournament
from config.constants import LIVE_ROUND_TYPE_6P, LIVE_ROUND_TYPE_SLAG, LIVE_ROUND_TYPES
from src import my_dfs


LIVE_ROUNDS_TABLE = "live_runder"
LIVE_TABLE_PREFIX = "live_runde_"
LIVE_ROUND_COLUMNS = ["live_rundeid", "source_rundeid", "score_table", "created_at", "tittel", "type_runde", "antall_runder", "spillere", "rundeoppsett"]
logger = logging.getLogger(__name__)


class LiveRoundError(RuntimeError):
    """Raised when a temporary live round cannot be created or loaded."""


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _live_score_table_name(source_rundeid: str, round_number: int = 1) -> str:
    return f"{LIVE_TABLE_PREFIX}{source_rundeid}_runde_{round_number}"


def _get_live_rounds_df() -> pd.DataFrame:
    cached = get_cached_df(LIVE_ROUNDS_TABLE)
    if cached is not None and not cached.empty:
        live_rounds_df = cached.copy()
    else:
        if not table_exists(LIVE_ROUNDS_TABLE):
            return pd.DataFrame(columns=LIVE_ROUND_COLUMNS)
        live_rounds_df = get_sqlite_df(LIVE_ROUNDS_TABLE, strict=True)
        if not live_rounds_df.empty:
            set_cached_df(LIVE_ROUNDS_TABLE, live_rounds_df)

    required_columns = LIVE_ROUND_COLUMNS[:4]
    missing_columns = set(required_columns).difference(live_rounds_df.columns)
    if missing_columns:
        missing_display = ", ".join(sorted(missing_columns))
        raise LiveRoundError(f"live_runder mangler kolonner: {missing_display}")
    for column, default_value in {"tittel": "", "type_runde": LIVE_ROUND_TYPE_SLAG, "antall_runder": 1, "spillere": "[]", "rundeoppsett": "[]"}.items():
        if column not in live_rounds_df.columns:
            live_rounds_df[column] = default_value
    return live_rounds_df


def _save_live_rounds_df(live_rounds_df: pd.DataFrame) -> None:
    if not my_dfs.save_table_df(LIVE_ROUNDS_TABLE, live_rounds_df):
        raise LiveRoundError("Klarte ikke å lagre metadata for Live Runde.")
    try:
        set_cached_df(LIVE_ROUNDS_TABLE, live_rounds_df)
    except Exception:
        pass


def _set_slag_runde_ind(rundeid: str, value: int) -> None:
    """Flag/unflag the source round as tied to an active live round in local SQLite."""
    round_info_df = my_dfs.get_round_info_df()
    if round_info_df is None or round_info_df.empty or "rundeid" not in round_info_df.columns:
        raise LiveRoundError("Fant ingen data i rundeinfo.")

    updated_round_info_df = round_info_df.copy()
    if "slag_runde_ind" not in updated_round_info_df.columns:
        updated_round_info_df["slag_runde_ind"] = 0

    row_mask = updated_round_info_df["rundeid"].astype(str) == str(rundeid)
    if not row_mask.any():
        raise LiveRoundError(f"Fant ikke rundeinfo for rundeid {rundeid}")

    updated_round_info_df.loc[row_mask, "slag_runde_ind"] = value
    if not my_dfs.save_round_info_df(updated_round_info_df):
        raise LiveRoundError(f"Klarte ikke å oppdatere slag_runde_ind for rundeid {rundeid}.")


def _build_player_setup(
    group_1: list[str], group_2: list[str], startverdier: dict[str, int | float] | None,
) -> list[dict[str, str | int | float]]:
    normalized_groups = []
    for group_number, player_names in enumerate([group_1, group_2], start=1):
        names = [str(player_name).strip() for player_name in player_names if str(player_name).strip()]
        if len(names) > 4:
            raise LiveRoundError(f"Gruppe {group_number} kan ha maksimalt fire spillere.")
        normalized_groups.append(names)

    selected_players = normalized_groups[0] + normalized_groups[1]
    if not selected_players:
        raise LiveRoundError("Velg minst én spiller.")
    if len(selected_players) != len(set(selected_players)):
        raise LiveRoundError("En spiller kan bare være med i én gruppe.")

    startverdier = startverdier or {}
    return [
        {
            "spiller": player_name,
            "gruppe": group_number,
            "startverdi": float(startverdier.get(player_name, 0)),
        }
        for group_number, player_names in enumerate(normalized_groups, start=1)
        for player_name in player_names
    ]


def get_live_round_candidates() -> pd.DataFrame:
    """Return ordinary, unfinished rounds that do not already have a live session."""
    round_info_df = my_dfs.get_round_info_df()
    if round_info_df is None or round_info_df.empty:
        return pd.DataFrame(columns=["rundeid", "turneringsid", "runde", "bane"])

    required_columns = {"rundeid", "turneringsid", "runde", "bane", "ferdig_ind"}
    missing_columns = required_columns.difference(round_info_df.columns)
    if missing_columns:
        missing_display = ", ".join(sorted(missing_columns))
        raise LiveRoundError(f"rundeinfo mangler kolonner: {missing_display}")

    live_rounds_df = _get_live_rounds_df()
    active_source_ids = set(live_rounds_df["source_rundeid"].astype(str))
    for rundeoppsett_json in live_rounds_df.get("rundeoppsett", pd.Series(dtype=str)):
        try:
            for round_setup in json.loads(str(rundeoppsett_json or "[]")):
                if round_setup.get("rundeid"):
                    active_source_ids.add(str(round_setup["rundeid"]))
        except json.JSONDecodeError:
            continue
    candidates_df = round_info_df.loc[
        pd.to_numeric(round_info_df["ferdig_ind"], errors="coerce").fillna(0).eq(0),
        ["rundeid", "turneringsid", "runde", "bane"],
    ].copy()
    candidates_df["rundeid"] = candidates_df["rundeid"].astype(str)
    candidates_df = candidates_df.loc[~candidates_df["rundeid"].isin(active_source_ids)]
    return candidates_df.sort_values(["turneringsid", "runde", "rundeid"]).reset_index(drop=True)


def get_active_live_rounds() -> pd.DataFrame:
    """Return temporary live sessions with source-round metadata for UI cards."""
    live_rounds_df = _get_live_rounds_df()
    if live_rounds_df.empty:
        return pd.DataFrame(columns=LIVE_ROUND_COLUMNS + ["turneringsid", "runde", "bane"])

    round_info_df = my_dfs.get_round_info_df()
    if round_info_df is None or round_info_df.empty:
        return live_rounds_df.copy()

    metadata_df = round_info_df[["rundeid", "turneringsid", "runde", "bane"]].copy()
    metadata_df["rundeid"] = metadata_df["rundeid"].astype(str)
    active_df = live_rounds_df.copy()
    active_df["source_rundeid"] = active_df["source_rundeid"].astype(str)
    return active_df.merge(metadata_df, left_on="source_rundeid", right_on="rundeid", how="left").drop(columns=["rundeid"])


def get_live_round_details(live_rundeid: str) -> dict:
    """Return one active live session with its decoded setup metadata."""
    active_rounds_df = get_active_live_rounds()
    target_id = str(live_rundeid).strip()
    session_df = active_rounds_df.loc[active_rounds_df["live_rundeid"].astype(str).str.strip() == target_id]
    if session_df.empty:
        raise LiveRoundError("Fant ikke den aktive live-runden.")

    session = session_df.iloc[0].to_dict()
    try:
        session["spillere"] = json.loads(str(session.get("spillere") or "[]"))
        session["rundeoppsett"] = json.loads(str(session.get("rundeoppsett") or "[]"))
    except json.JSONDecodeError as exc:
        raise LiveRoundError("Live-runden har ugyldig spilleroppsett.") from exc
    if not session["rundeoppsett"]:
        session["rundeoppsett"] = [{
            "runde": 1,
            "rundeid": str(session.get("source_rundeid") or ""),
            "nyopprettet": False,
            "score_table": str(session.get("score_table") or session["live_rundeid"]),
            "startverdier": {player["spiller"]: player["startverdi"] for player in session["spillere"]},
            "gruppe_klar": {"1": [], "2": []},
            "fullfort": False,
        }]
    return session


def _get_round_setup(session: dict, round_number: int | None = None) -> dict:
    for round_setup in session["rundeoppsett"]:
        if not round_setup.get("fullfort", False):
            current_round = int(round_setup["runde"])
            break
    else:
        current_round = int(session["rundeoppsett"][-1]["runde"])
    requested_round = current_round if round_number is None else int(round_number)
    for round_setup in session["rundeoppsett"]:
        if int(round_setup["runde"]) == requested_round:
            return round_setup
    raise LiveRoundError(f"Fant ikke live-runde {requested_round}.")


def get_live_round_access(live_rundeid: str, current_player: str) -> dict:
    session = get_live_round_details(live_rundeid)
    for player in session["spillere"]:
        if str(player["spiller"]) == str(current_player):
            return {"session": session, "gruppe": int(player["gruppe"]), "spillere": [item["spiller"] for item in session["spillere"] if int(item["gruppe"]) == int(player["gruppe"])]}
    raise LiveRoundError("Du er ikke registrert i denne live-runden.")


def _get_round_score_df(round_setup: dict) -> pd.DataFrame:
    score_table = str(round_setup["score_table"])
    cached = get_cached_df(score_table)
    if cached is not None and not cached.empty:
        return cached.copy()
    if not table_exists(score_table):
        raise LiveRoundError("Fant ikke scorekortet for den aktive live-runden.")
    score_df = get_sqlite_df(score_table, strict=True)
    if not score_df.empty:
        set_cached_df(score_table, score_df)
    return score_df


def _get_par_by_hull(session: dict) -> dict[int, int]:
    hole_info_df = my_dfs.get_hole_info_df()
    required_columns = {"bane", "hull", "par"}
    if hole_info_df is None or required_columns.difference(hole_info_df.columns):
        raise LiveRoundError("Fant ikke parinformasjon for live-runden.")
    par_df = hole_info_df.loc[hole_info_df["bane"].astype(str) == str(session["bane"]), ["hull", "par"]].copy()
    par_df["hull"] = pd.to_numeric(par_df["hull"], errors="coerce")
    par_df["par"] = pd.to_numeric(par_df["par"], errors="coerce")
    return {int(row["hull"]): int(row["par"]) for _, row in par_df.dropna().iterrows()}


def _published_hulls(round_setup: dict) -> set[int]:
    group_status = round_setup.get("gruppe_klar", {})
    return set(group_status.get("1", [])).intersection(group_status.get("2", []))


def _fresh_session_in_transaction(conn, live_rundeid: str, fallback_session: dict) -> tuple[dict, pd.DataFrame]:
    live_rounds_df = get_sqlite_df(LIVE_ROUNDS_TABLE, strict=True, connection=conn)
    row_mask = live_rounds_df["live_rundeid"].astype(str) == str(live_rundeid)
    if not row_mask.any():
        raise LiveRoundError("Fant ikke den aktive live-runden.")
    session = {**fallback_session, **live_rounds_df.loc[row_mask].iloc[0].to_dict()}
    try:
        session["spillere"] = json.loads(str(session.get("spillere") or "[]"))
        session["rundeoppsett"] = json.loads(str(session.get("rundeoppsett") or "[]"))
    except json.JSONDecodeError as exc:
        raise LiveRoundError("Live-runden har ugyldig spilleroppsett.") from exc
    return session, live_rounds_df


def _clear_live_session_cache(score_table: str) -> None:
    clear_cached_df(LIVE_ROUNDS_TABLE)
    clear_cached_df(score_table)


def _save_live_scores(
    live_rundeid: str,
    current_player: str,
    hull: int,
    scores: dict[str, int],
    *,
    require_complete_group: bool,
) -> None:
    access = get_live_round_access(live_rundeid, current_player)
    player_names = access["spillere"]
    if not scores or not set(scores).issubset(player_names):
        raise LiveRoundError("Du kan bare registrere spillere i din egen gruppe.")
    if require_complete_group and set(scores) != set(player_names):
        raise LiveRoundError("Alle spillere i gruppen må ha ett slag før hullet lagres.")

    par = _get_par_by_hull(access["session"]).get(int(hull))
    if par is None:
        raise LiveRoundError(f"Fant ikke par for hull {hull}.")
    normalized_scores = {}
    for player_name, score in scores.items():
        if not isinstance(score, int) or isinstance(score, bool):
            raise LiveRoundError("Slag må være et heltall.")
        if score < 1 or score > par + 6:
            raise LiveRoundError(f"Slag må være mellom 1 og {par + 6} på dette hullet.")
        normalized_scores[player_name] = score

    with db.transaction(immediate=True) as conn:
        session, _ = _fresh_session_in_transaction(conn, live_rundeid, access["session"])
        round_setup = _get_round_setup(session)
        score_table = str(round_setup["score_table"])
        score_df = get_sqlite_df(score_table, strict=True, connection=conn)
        if hull not in set(pd.to_numeric(score_df["hull"], errors="coerce").dropna().astype(int)):
            raise LiveRoundError(f"Hull {hull} finnes ikke i denne runden.")
        missing_columns = set(normalized_scores).difference(score_df.columns)
        if missing_columns:
            raise LiveRoundError("Scorekortet mangler en eller flere spillere.")

        update_sqlite_row(conn, score_table, "hull", hull, normalized_scores)
        group_status = round_setup.setdefault("gruppe_klar", {"1": [], "2": []})
        group_key = str(access["gruppe"])
        group_status[group_key] = [value for value in group_status.get(group_key, []) if int(value) != int(hull)]
        update_sqlite_row(
            conn,
            LIVE_ROUNDS_TABLE,
            "live_rundeid",
            str(live_rundeid),
            {"rundeoppsett": json.dumps(session["rundeoppsett"])},
        )

    _clear_live_session_cache(score_table)


def save_live_score(live_rundeid: str, current_player: str, player_name: str, hull: int, score: int) -> None:
    _save_live_scores(
        live_rundeid,
        current_player,
        hull,
        {player_name: score},
        require_complete_group=False,
    )


def save_live_hole_scores(live_rundeid: str, current_player: str, hull: int, scores: dict[str, int]) -> None:
    """Save all scores for the active group on one hole in a single SQLite write."""
    if not isinstance(scores, dict):
        raise LiveRoundError("Slagene må sendes som én verdi per spiller.")
    _save_live_scores(
        live_rundeid,
        current_player,
        hull,
        scores,
        require_complete_group=True,
    )


def confirm_live_hole(live_rundeid: str, current_player: str, hull: int) -> bool:
    access = get_live_round_access(live_rundeid, current_player)
    with db.transaction(immediate=True) as conn:
        session, _ = _fresh_session_in_transaction(conn, live_rundeid, access["session"])
        round_setup = _get_round_setup(session)
        score_table = str(round_setup["score_table"])
        score_df = get_sqlite_df(score_table, strict=True, connection=conn)
        hole_df = score_df.loc[pd.to_numeric(score_df["hull"], errors="coerce").eq(hull), access["spillere"]]
        if hole_df.empty or hole_df.isna().any(axis=None):
            raise LiveRoundError("Alle spillere i gruppen må ha slag før dere går videre.")

        group_status = round_setup.setdefault("gruppe_klar", {"1": [], "2": []})
        group_key = str(access["gruppe"])
        group_status[group_key] = sorted(set(group_status.get(group_key, []) + [int(hull)]))
        is_published = int(hull) in _published_hulls(round_setup)
        all_holes = set(pd.to_numeric(score_df["hull"], errors="coerce").dropna().astype(int))
        if is_published and all_holes and int(hull) == max(all_holes):
            round_setup["fullfort"] = True

        update_sqlite_row(
            conn,
            LIVE_ROUNDS_TABLE,
            "live_rundeid",
            str(live_rundeid),
            {"rundeoppsett": json.dumps(session["rundeoppsett"])},
        )

    _clear_live_session_cache(score_table)
    return is_published


def _live_points_long_df(
    score_df: pd.DataFrame, par_by_hull: dict[int, int], published_hulls: set[int], player_names: list[str]
) -> pd.DataFrame:
    """Long-format (hull, spiller, p6) for published holes, ranking all players in the live round together (used for 6P)."""
    empty_columns = ["hull", "spiller", "p6"]
    if not published_hulls:
        return pd.DataFrame(columns=empty_columns)
    long_rows = []
    for _, row in score_df.iterrows():
        hull_value = row["hull"]
        if pd.isna(hull_value) or int(hull_value) not in published_hulls:
            continue
        hull = int(hull_value)
        par = par_by_hull.get(hull)
        if par is None:
            continue
        for player_name in player_names:
            slag = row.get(player_name)
            if pd.isna(slag):
                continue
            long_rows.append({"rundeid": "live", "hull": hull, "spiller": player_name, "slag": float(slag), "par": par})
    if not long_rows:
        return pd.DataFrame(columns=empty_columns)
    long_df = pd.DataFrame(long_rows)
    long_df = recalculate_placement(long_df)
    long_df = recalculate_6points(long_df)
    return long_df[empty_columns]


def _compute_live_points(
    score_df: pd.DataFrame, par_by_hull: dict[int, int], published_hulls: set[int], player_names: list[str]
) -> dict[str, float]:
    """Sum P6 points per player across published holes (used for 6P)."""
    long_df = _live_points_long_df(score_df, par_by_hull, published_hulls, player_names)
    if long_df.empty:
        return {}
    totals = long_df.groupby("spiller")["p6"].sum()
    return {str(spiller): float(total) for spiller, total in totals.items()}


def get_live_hole_points(
    score_df: pd.DataFrame, par_by_hull: dict[int, int], published_hulls: set[int], player_names: list[str]
) -> dict[tuple[int, str], float]:
    """Per-hole P6 points for published holes only (used by the 'Alle slag' Poeng toggle)."""
    long_df = _live_points_long_df(score_df, par_by_hull, published_hulls, player_names)
    return {(int(row["hull"]), str(row["spiller"])): float(row["p6"]) for _, row in long_df.iterrows()}


def get_live_overview(live_rundeid: str, current_player: str) -> pd.DataFrame:
    access = get_live_round_access(live_rundeid, current_player)
    session = access["session"]
    round_setup = _get_round_setup(session)
    score_df = _get_round_score_df(round_setup)
    published_hulls = _published_hulls(round_setup)
    par_by_hull = _get_par_by_hull(session)
    is_6p = session.get("type_runde") == LIVE_ROUND_TYPE_6P
    player_names = [item["spiller"] for item in session["spillere"]]
    points_by_player = _compute_live_points(score_df, par_by_hull, published_hulls, player_names) if is_6p else {}
    rows = []
    for player_name in player_names:
        is_own_group = player_name in access["spillere"]
        visible_hulls = (
            set(pd.to_numeric(score_df["hull"], errors="coerce").dropna().astype(int))
            if is_own_group
            else published_hulls
        )
        player_scores = score_df.loc[score_df["hull"].isin(visible_hulls), ["hull", player_name]].copy()
        scores = pd.to_numeric(player_scores[player_name], errors="coerce")
        par_total = sum(par_by_hull.get(int(hull), 0) for hull in player_scores.loc[scores.notna(), "hull"])
        startverdi = int(round_setup.get("startverdier", {}).get(player_name, 0))
        rundens_slag = int(scores.sum())
        if is_own_group or published_hulls:
            row = {"spiller": player_name, "spillers_par": startverdi + int(scores.sum()) - par_total, "rundens_slag": rundens_slag}
            if is_6p:
                start_poeng = round_setup.get("start_poeng", {}).get(player_name, 0)
                row["poeng"] = float(start_poeng) + points_by_player.get(player_name, 0.0)
            rows.append(row)
    overview_df = pd.DataFrame(rows)
    if is_6p and "poeng" in overview_df.columns:
        overview_df = overview_df.sort_values(["poeng", "spillers_par", "spiller"], ascending=[False, True, True]).reset_index(drop=True)
    else:
        overview_df = overview_df.sort_values(["spillers_par", "spiller"]).reset_index(drop=True)
    overview_df.insert(0, "plassering", range(1, len(overview_df) + 1))
    return overview_df


def get_live_round_state(live_rundeid: str, current_player: str) -> dict:
    access = get_live_round_access(live_rundeid, current_player)
    round_setup = _get_round_setup(access["session"])
    return {
        **access,
        "runde": int(round_setup["runde"]),
        "score_df": _get_round_score_df(round_setup),
        "par_by_hull": _get_par_by_hull(access["session"]),
        "published_hulls": _published_hulls(round_setup),
        "group_confirmed_hulls": set(round_setup.get("gruppe_klar", {}).get(str(access["gruppe"]), [])),
        "fullfort": bool(round_setup.get("fullfort", False)),
        "antall_runder": int(access["session"].get("antall_runder", 1)),
    }


def refresh_live_round_cache(live_rundeid: str) -> None:
    """Force the next live-round render to read metadata and scores from local SQLite."""
    clear_cached_df(LIVE_ROUNDS_TABLE)
    session = get_live_round_details(live_rundeid)
    round_setup = _get_round_setup(session)
    clear_cached_df(str(round_setup["score_table"]))


def _final_standings(session: dict, round_setup: dict) -> dict[str, int]:
    """Compute each player's spillers_par (startverdi + slag - par) for a finished round, regardless of publish-status."""
    score_df = _get_round_score_df(round_setup)
    par_by_hull = _get_par_by_hull(session)
    startverdier = round_setup.get("startverdier", {})
    standings = {}
    for player in session["spillere"]:
        player_name = player["spiller"]
        scores = pd.to_numeric(score_df.get(player_name, pd.Series(dtype=float)), errors="coerce")
        par_total = sum(par_by_hull.get(int(hull), 0) for hull in score_df.loc[scores.notna(), "hull"])
        standings[player_name] = int(startverdier.get(player_name, 0)) + int(scores.sum()) - par_total
    return standings


def _build_completed_live_round_df(session: dict) -> pd.DataFrame:
    """Build one ordinary scorecard from all completed live-round scorecards."""
    source_round_df = my_dfs.get_round_df(str(session["source_rundeid"]))
    if source_round_df is None or source_round_df.empty or "hull" not in source_round_df.columns:
        raise LiveRoundError("Fant ikke scorekortmalen for ferdig live-runde.")
    player_names = [str(player["spiller"]) for player in session.get("spillere", [])]
    round_score_dfs = [_get_round_score_df(round_setup) for round_setup in session["rundeoppsett"]]
    try:
        return calculate_live_round_df(source_round_df, round_score_dfs, player_names)
    except ValueError as exc:
        raise LiveRoundError(f"Klarte ikke å beregne ferdig live-runde: {exc}") from exc

def _save_completed_live_round(session: dict):
    """Commit a finished live session as the selected ordinary round."""
    source_rundeid = str(session["source_rundeid"])
    completed_df = _build_completed_live_round_df(session)
    source_round_df = my_dfs.get_round_df(source_rundeid)
    prepared_df = source_round_df.copy()
    for player_name in [str(player["spiller"]) for player in session.get("spillere", [])]:
        if player_name not in prepared_df.columns:
            prepared_df[player_name] = pd.NA

    try:
        return save_round_and_sync(source_rundeid, prepared_df, completed_df, is_round_completed=True)
    except RoundSaveError as exc:
        raise LiveRoundError(f"Live-runden er ferdig, men kunne ikke legges til som vanlig runde: {exc}") from exc


def _save_single_live_round(session: dict, round_setup: dict):
    """Commit one live round's own scorecard directly as its own ordinary round, without averaging (used for 6P)."""
    rundeid = str(round_setup.get("rundeid") or session["source_rundeid"])
    score_df = _get_round_score_df(round_setup)
    source_round_df = my_dfs.get_round_df(rundeid)
    if source_round_df is None or source_round_df.empty:
        raise LiveRoundError(f"Fant ikke scorekortmalen for runde {rundeid}.")
    prepared_df = source_round_df.copy()
    for player_name in [str(player["spiller"]) for player in session.get("spillere", [])]:
        if player_name not in prepared_df.columns:
            prepared_df[player_name] = pd.NA

    try:
        return save_round_and_sync(rundeid, prepared_df, score_df, is_round_completed=True)
    except RoundSaveError as exc:
        raise LiveRoundError(f"Runden er ferdig, men kunne ikke lagres som vanlig runde: {exc}") from exc


def _save_round_setup(live_rundeid: str, session: dict) -> None:
    live_rounds_df = _get_live_rounds_df()
    row_mask = live_rounds_df["live_rundeid"].astype(str) == str(live_rundeid)
    live_rounds_df.loc[row_mask, "rundeoppsett"] = json.dumps(session["rundeoppsett"])
    _save_live_rounds_df(live_rounds_df)


def advance_to_next_live_round(live_rundeid: str, current_player: str) -> int:
    """Complete the active round and start the next one."""
    access = get_live_round_access(live_rundeid, current_player)
    session = access["session"]
    round_setup = _get_round_setup(session)
    round_number = int(round_setup["runde"])
    antall_runder = int(session.get("antall_runder", 1))
    if round_number >= antall_runder:
        raise LiveRoundError("Det finnes ingen flere runder å hoppe til.")

    if session.get("type_runde") == LIVE_ROUND_TYPE_6P:
        return _advance_to_next_6p_round(live_rundeid, session, round_setup)

    standings = _final_standings(session, round_setup)
    round_setup["fullfort"] = True

    source_round_df = my_dfs.get_round_df(str(session["source_rundeid"]))
    if source_round_df is None or source_round_df.empty or "hull" not in source_round_df.columns:
        raise LiveRoundError("Fant ikke scorekortmal for neste runde.")

    next_round_number = round_number + 1
    next_score_table = _live_score_table_name(str(session["source_rundeid"]), next_round_number)
    next_score_df = source_round_df[["hull"]].copy()
    for player in session["spillere"]:
        next_score_df[player["spiller"]] = pd.NA

    session["rundeoppsett"].append(
        {
            "runde": next_round_number,
            "score_table": next_score_table,
            "startverdier": standings,
            "gruppe_klar": {"1": [], "2": []},
            "fullfort": False,
        }
    )

    if not my_dfs.save_table_df(next_score_table, next_score_df):
        raise LiveRoundError("Klarte ikke å opprette scorekort for neste runde.")
    _save_round_setup(live_rundeid, session)
    try:
        set_cached_df(next_score_table, next_score_df)
    except Exception:
        pass

    return next_round_number


def _advance_to_next_6p_round(live_rundeid: str, session: dict, round_setup: dict) -> int:
    """Create a new, separate tournament round for the next 6P round (no averaging), reusing the same bane."""
    round_number = int(round_setup["runde"])
    current_rundeid = str(round_setup.get("rundeid") or session["source_rundeid"])
    round_info_df = my_dfs.get_round_info_df()
    current_round_info = round_info_df.loc[round_info_df["rundeid"].astype(str) == current_rundeid] if round_info_df is not None else pd.DataFrame()
    if current_round_info.empty:
        raise LiveRoundError(f"Fant ikke rundeinfo for {current_rundeid}.")
    turneringsid = str(current_round_info.iloc[0]["turneringsid"])
    bane = str(current_round_info.iloc[0]["bane"])
    player_names = [str(player["spiller"]) for player in session.get("spillere", [])]

    next_round_number = round_number + 1
    next_rundeid = create_round_in_tournament(turneringsid, bane, player_names, sync_to_gsheet=False)
    next_score_table = _live_score_table_name(next_rundeid, next_round_number)
    next_round_df = my_dfs.get_round_df(next_rundeid)
    next_score_df = next_round_df[["hull"]].copy()
    for player_name in player_names:
        next_score_df[player_name] = pd.NA

    session["rundeoppsett"].append(
        {
            "runde": next_round_number,
            "rundeid": next_rundeid,
            "nyopprettet": True,
            "score_table": next_score_table,
            "startverdier": {player_name: 0 for player_name in player_names},
            "start_poeng": get_tournament_p6_totals(turneringsid),
            "gruppe_klar": {"1": [], "2": []},
            "fullfort": False,
        }
    )

    if not my_dfs.save_table_df(next_score_table, next_score_df):
        raise LiveRoundError("Klarte ikke å opprette scorekort for neste runde.")
    _save_round_setup(live_rundeid, session)
    try:
        set_cached_df(next_score_table, next_score_df)
    except Exception:
        pass

    return next_round_number


def reset_live_round(live_rundeid: str) -> None:
    """Clear all registered scores and confirmed holes for all players in a live session."""
    session = get_live_round_details(live_rundeid)
    player_names = [item["spiller"] for item in session.get("spillere", [])]
    for round_setup in session.get("rundeoppsett", []):
        score_table = str(round_setup["score_table"])
        if table_exists(score_table):
            score_df = get_sqlite_df(score_table, strict=True)
            for player_name in player_names:
                if player_name in score_df.columns:
                    score_df[player_name] = pd.NA
            if not my_dfs.save_table_df(score_table, score_df):
                raise LiveRoundError("Klarte ikke å tilbakestille scorekortet.")
            try:
                set_cached_df(score_table, score_df)
            except Exception:
                pass
        round_setup["gruppe_klar"] = {"1": [], "2": []}
        round_setup["fullfort"] = False

    live_rounds_df = _get_live_rounds_df()
    row_mask = live_rounds_df["live_rundeid"].astype(str) == str(live_rundeid)
    live_rounds_df.loc[row_mask, "rundeoppsett"] = json.dumps(session["rundeoppsett"])
    _save_live_rounds_df(live_rounds_df)


def create_live_round(
    source_rundeid: str | None,
    tittel: str,
    group_1: list[str],
    group_2: list[str],
    startverdier: dict[str, int | float] | None = None,
    type_runde: str = LIVE_ROUND_TYPE_SLAG,
    antall_runder: int = 1,
    new_round_turneringsid: str | None = None,
    new_round_bane: str | None = None,
) -> str:
    """Create an isolated live scorecard from the selected setup players."""
    tittel = str(tittel).strip()
    if not tittel:
        raise LiveRoundError("Tittel må fylles ut.")
    if type_runde not in LIVE_ROUND_TYPES:
        raise LiveRoundError(f"Ukjent rundetype: {type_runde}.")
    if antall_runder not in {1, 2, 3}:
        raise LiveRoundError("Antall runder må være 1, 2 eller 3.")

    player_setup = _build_player_setup(group_1, group_2, None if type_runde == LIVE_ROUND_TYPE_6P else startverdier)

    newly_created_round = False
    if source_rundeid is None:
        if type_runde != LIVE_ROUND_TYPE_6P or not new_round_turneringsid or not new_round_bane:
            raise LiveRoundError("Velg en runde, eller oppgi turnering og bane for å opprette en ny.")
        source_rundeid = create_round_in_tournament(
            str(new_round_turneringsid),
            str(new_round_bane),
            group_1 + group_2,
            sync_to_gsheet=False,
        )
        newly_created_round = True
    source_rundeid = str(source_rundeid)

    candidates_df = get_live_round_candidates()
    if source_rundeid not in set(candidates_df["rundeid"]):
        if newly_created_round:
            delete_round_from_tournament(source_rundeid, sync_to_gsheet=False)
        raise LiveRoundError(f"Runde {source_rundeid} er ikke tilgjengelig for Live Runde.")

    start_poeng = None
    if type_runde == LIVE_ROUND_TYPE_6P:
        turneringsid = str(candidates_df.loc[candidates_df["rundeid"] == source_rundeid, "turneringsid"].iloc[0])
        start_poeng = get_tournament_p6_totals(turneringsid)

    source_round_df = my_dfs.get_round_df(source_rundeid)
    if source_round_df is None or source_round_df.empty:
        raise LiveRoundError(f"Fant ingen scoredata for runde {source_rundeid}.")

    if "hull" not in source_round_df.columns:
        raise LiveRoundError(f"Runde {source_rundeid} mangler hull-kolonnen.")

    live_score_df = source_round_df[["hull"]].copy()
    for player in player_setup:
        live_score_df[player["spiller"]] = pd.NA

    score_table = _live_score_table_name(source_rundeid)
    live_rundeid = score_table
    live_rounds_df = _get_live_rounds_df()
    first_round_setup = {
        "runde": 1,
        "rundeid": source_rundeid,
        "nyopprettet": newly_created_round,
        "score_table": score_table,
        "startverdier": {player["spiller"]: player["startverdi"] for player in player_setup},
        "gruppe_klar": {"1": [], "2": []},
        "fullfort": False,
    }
    if start_poeng is not None:
        first_round_setup["start_poeng"] = start_poeng
    new_row = pd.DataFrame(
        [{
            "live_rundeid": live_rundeid,
            "source_rundeid": source_rundeid,
            "score_table": score_table,
            "created_at": _timestamp(),
            "tittel": tittel,
            "type_runde": type_runde,
            "antall_runder": antall_runder,
            "spillere": json.dumps(player_setup),
            "rundeoppsett": json.dumps([first_round_setup]),
        }]
    )
    updated_live_rounds_df = pd.concat([live_rounds_df, new_row], ignore_index=True)

    if not my_dfs.save_table_df(score_table, live_score_df):
        raise LiveRoundError(f"Klarte ikke å opprette midlertidig live-runde for {source_rundeid}.")
    if not my_dfs.save_table_df(LIVE_ROUNDS_TABLE, updated_live_rounds_df):
        raise LiveRoundError("Klarte ikke å lagre metadata for Live Runde.")

    try:
        set_cached_df(score_table, live_score_df)
        set_cached_df(LIVE_ROUNDS_TABLE, updated_live_rounds_df)
    except Exception:
        pass

    if type_runde == LIVE_ROUND_TYPE_SLAG:
        _set_slag_runde_ind(source_rundeid, 1)

    return live_rundeid


def delete_live_round(live_rundeid: str) -> None:
    """Remove a live round from the active list; registered score tables are left in place but become unreachable."""
    live_rounds_df = _get_live_rounds_df()
    row_mask = live_rounds_df["live_rundeid"].astype(str) == str(live_rundeid)
    if not row_mask.any():
        raise LiveRoundError("Fant ikke den aktive live-runden.")
    session_row = live_rounds_df.loc[row_mask].iloc[0]
    source_rundeid = str(session_row["source_rundeid"])
    type_runde = str(session_row.get("type_runde") or LIVE_ROUND_TYPE_SLAG)

    if type_runde == LIVE_ROUND_TYPE_6P:
        try:
            rundeoppsett = json.loads(str(session_row.get("rundeoppsett") or "[]"))
        except json.JSONDecodeError:
            rundeoppsett = []
        for round_setup in rundeoppsett:
            rundeid = str(round_setup.get("rundeid") or "")
            if rundeid and round_setup.get("nyopprettet"):
                delete_round_from_tournament(rundeid, sync_to_gsheet=False)
        _save_live_rounds_df(live_rounds_df.loc[~row_mask].reset_index(drop=True))
        return

    _save_live_rounds_df(live_rounds_df.loc[~row_mask].reset_index(drop=True))
    _set_slag_runde_ind(source_rundeid, 0)


def update_live_round_setup(
    live_rundeid: str,
    tittel: str,
    group_1: list[str],
    group_2: list[str],
    startverdier: dict[str, int | float] | None = None,
    antall_runder: int = 1,
) -> None:
    """Update title, player setup and startverdier for round 1 of an existing live round; players can only change while round 1 has no registered scores."""
    tittel = str(tittel).strip()
    if not tittel:
        raise LiveRoundError("Tittel må fylles ut.")
    if antall_runder not in {1, 2, 3}:
        raise LiveRoundError("Antall runder må være 1, 2 eller 3.")

    session = get_live_round_details(live_rundeid)
    new_player_setup = _build_player_setup(group_1, group_2, startverdier)
    new_player_names = {player["spiller"] for player in new_player_setup}
    old_player_names = {player["spiller"] for player in session["spillere"]}

    first_round_setup = session["rundeoppsett"][0]
    score_df = _get_round_score_df(first_round_setup)
    has_scores = any(
        player_name in score_df.columns and score_df[player_name].notna().any() for player_name in old_player_names
    )
    if has_scores and new_player_names != old_player_names:
        raise LiveRoundError("Kan ikke endre spillerne etter at slag er registrert.")

    if new_player_names != old_player_names:
        for player_name in new_player_names - old_player_names:
            score_df[player_name] = pd.NA
        score_df = score_df[["hull"] + [player["spiller"] for player in new_player_setup]]
        if not my_dfs.save_table_df(str(first_round_setup["score_table"]), score_df):
            raise LiveRoundError("Klarte ikke å oppdatere scorekortet.")
        try:
            set_cached_df(str(first_round_setup["score_table"]), score_df)
        except Exception:
            pass

    first_round_setup["startverdier"] = {player["spiller"]: player["startverdi"] for player in new_player_setup}
    if session.get("type_runde") == LIVE_ROUND_TYPE_6P:
        round_info_df = my_dfs.get_round_info_df()
        rundeid = str(first_round_setup.get("rundeid") or session.get("source_rundeid"))
        turneringsid_row = round_info_df.loc[round_info_df["rundeid"].astype(str) == rundeid] if round_info_df is not None else pd.DataFrame()
        if not turneringsid_row.empty:
            first_round_setup["start_poeng"] = get_tournament_p6_totals(str(turneringsid_row.iloc[0]["turneringsid"]))

    live_rounds_df = _get_live_rounds_df()
    row_mask = live_rounds_df["live_rundeid"].astype(str) == str(live_rundeid)
    if not row_mask.any():
        raise LiveRoundError("Fant ikke den aktive live-runden.")
    live_rounds_df.loc[row_mask, "tittel"] = tittel
    live_rounds_df.loc[row_mask, "antall_runder"] = antall_runder
    live_rounds_df.loc[row_mask, "spillere"] = json.dumps(new_player_setup)
    live_rounds_df.loc[row_mask, "rundeoppsett"] = json.dumps(session["rundeoppsett"])
    _save_live_rounds_df(live_rounds_df)


def _set_finalization_status(live_rundeid: str, fallback_session: dict, status: str) -> dict:
    with db.transaction(immediate=True) as conn:
        session, _ = _fresh_session_in_transaction(conn, live_rundeid, fallback_session)
        final_setup = session["rundeoppsett"][-1]
        final_setup["finalization_status"] = status
        update_sqlite_row(
            conn,
            LIVE_ROUNDS_TABLE,
            "live_rundeid",
            str(live_rundeid),
            {"rundeoppsett": json.dumps(session["rundeoppsett"])},
        )
    clear_cached_df(LIVE_ROUNDS_TABLE)
    return session


def finalize_live_round_session(live_rundeid: str, current_player: str) -> None:
    """Persist and sync a fully completed live session exactly at the end-page boundary."""
    access = get_live_round_access(live_rundeid, current_player)
    with db.transaction(immediate=True) as conn:
        session, _ = _fresh_session_in_transaction(conn, live_rundeid, access["session"])
        round_setups = session.get("rundeoppsett", [])
        if not round_setups or not all(bool(round_setup.get("fullfort")) for round_setup in round_setups):
            raise LiveRoundError("Begge grupper må fullføre hele live-runden før sluttsynk.")

        final_setup = round_setups[-1]
        current_status = str(final_setup.get("finalization_status") or "")
        if current_status == "completed":
            return
        if current_status == "pending":
            raise LiveRoundError("Sluttsynk pågår allerede. Prøv igjen om litt.")
        final_setup["finalization_status"] = "pending"
        update_sqlite_row(
            conn,
            LIVE_ROUNDS_TABLE,
            "live_rundeid",
            str(live_rundeid),
            {"rundeoppsett": json.dumps(round_setups)},
        )

    clear_cached_df(LIVE_ROUNDS_TABLE)
    for round_setup in round_setups:
        clear_cached_df(str(round_setup["score_table"]))

    try:
        if session.get("type_runde") == LIVE_ROUND_TYPE_6P:
            results = [_save_single_live_round(session, round_setup) for round_setup in round_setups]
        else:
            _set_slag_runde_ind(str(session["source_rundeid"]), 0)
            results = [_save_completed_live_round(session)]
        if any(not result.sync_report.ok for result in results):
            raise LiveRoundError("Sluttsynk til Google Sheets ble ikke fullført.")
    except Exception as exc:
        _set_finalization_status(live_rundeid, session, "failed")
        if isinstance(exc, LiveRoundError):
            raise
        raise LiveRoundError(f"Sluttsynk feilet: {exc}") from exc

    _set_finalization_status(live_rundeid, session, "completed")