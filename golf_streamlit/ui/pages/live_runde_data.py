"""Data loading and pure row/state transforms for the Live Runde Slag page (no rendering)."""

import pandas as pd
import streamlit as st

from aiapi.live_round import LiveRoundError, get_live_overview, get_live_round_details, get_live_round_state


def _score_value(value) -> int | None:
    if pd.isna(value):
        return None
    return int(value)


def _build_overview_rows(overview_df: pd.DataFrame) -> list[dict]:
    has_poeng = "poeng" in overview_df.columns
    return [
        {
            "plassering": int(row["plassering"]),
            "spiller": str(row["spiller"]),
            "spillers_par": int(row["spillers_par"]),
            "rundens_slag": int(row["rundens_slag"]),
            **({"poeng": float(row["poeng"])} if has_poeng else {}),
        }
        for _, row in overview_df.iterrows()
    ]


def _build_all_scores_rows(
    score_df: pd.DataFrame,
    player_names: list[str],
    par_by_hull: dict[int, int],
    own_group_players: set[str] | None = None,
    published_hulls: set[int] | None = None,
    hole_points: dict[tuple[int, str], float] | None = None,
) -> list[dict]:
    score_rows = score_df[["hull"] + player_names].copy()
    score_rows["hull"] = pd.to_numeric(score_rows["hull"], errors="coerce")
    score_rows = score_rows.dropna(subset=["hull"]).sort_values("hull")
    own_players = own_group_players if own_group_players is not None else set(player_names)
    pub_hulls = published_hulls if published_hulls is not None else set()
    rows = []
    for _, row in score_rows.iterrows():
        hull = int(row["hull"])
        par = par_by_hull.get(hull)
        scores_dict = {}
        for player_name in player_names:
            if hole_points is not None:
                scores_dict[player_name] = hole_points.get((hull, player_name))
                continue
            is_own_group = player_name in own_players
            if is_own_group or (hull in pub_hulls):
                scores_dict[player_name] = _score_value(row[player_name])
            else:
                scores_dict[player_name] = None
        rows.append(
            {
                "hull": hull,
                "par": int(par) if par is not None else None,
                "max_score": int(par) + 6 if par is not None else None,
                "scores": scores_dict,
            }
        )
    return rows


def _get_acting_player(session: dict, current_player: str, active_group: int | None = None) -> tuple[str, int]:
    spillere = session.get("spillere", [])
    if not spillere:
        return current_player, 1

    player_group = None
    for p in spillere:
        if str(p.get("spiller")) == str(current_player):
            player_group = int(p.get("gruppe", 1))
            break

    if active_group is None:
        active_group = player_group if player_group is not None else 1

    group_players = [p["spiller"] for p in spillere if int(p.get("gruppe", 1)) == int(active_group)]

    if current_player in group_players:
        return current_player, active_group
    elif group_players:
        return group_players[0], active_group
    return current_player, active_group


def _first_unconfirmed_hole(holes: list[int], confirmed_holes: set[int]) -> int | None:
    """Return the lowest-numbered hole not yet confirmed by the active group."""
    return next((hole for hole in sorted(holes) if hole not in confirmed_holes), None)


def load_live_round_context() -> dict | None:
    """Resolve session, state and derived values for the current player; renders info/warning and returns None if nothing can be shown yet."""
    live_rundeid = st.session_state.get("live_session_id")
    current_player = st.session_state.get("innlogget_spiller")
    if not live_rundeid or not current_player:
        st.info("Velg en live-runde fra oversikten.")
        return None

    try:
        session = get_live_round_details(str(live_rundeid))
    except LiveRoundError as exc:
        st.warning(str(exc))
        return None

    active_group_req = st.session_state.get("live_active_group")
    acting_player, _ = _get_acting_player(session, str(current_player), active_group_req)

    try:
        state = get_live_round_state(str(live_rundeid), str(acting_player))
    except LiveRoundError as exc:
        st.warning(str(exc))
        return None

    round_number = state["runde"]
    player_names = state["spillere"]
    score_df = state["score_df"]
    holes = sorted(score_df["hull"].astype(int).tolist())
    base_key = f"{live_rundeid}_{round_number}_{state['gruppe']}"

    hole_key = f"live_hole_{base_key}"
    open_at_next_hole = st.session_state.pop("live_open_next_hole_for", None) == str(live_rundeid)
    next_unconfirmed_hole = _first_unconfirmed_hole(holes, state["group_confirmed_hulls"])
    if open_at_next_hole or st.session_state.get(hole_key) not in holes:
        st.session_state[hole_key] = next_unconfirmed_hole if next_unconfirmed_hole is not None else holes[-1]
    hole = st.session_state[hole_key]

    par = state["par_by_hull"].get(hole)
    if par is None:
        st.error(f"Fant ikke par for hull {hole}.")
        return None

    show_all_key = f"live_show_all_{base_key}"
    if show_all_key not in st.session_state:
        st.session_state[show_all_key] = False
    edit_all_scores_key = f"live_edit_all_scores_{base_key}"
    if edit_all_scores_key not in st.session_state:
        st.session_state[edit_all_scores_key] = False

    overview_df = get_live_overview(str(live_rundeid), str(acting_player))
    overview_players = overview_df["spiller"].tolist() if not overview_df.empty else []
    all_setup_players = [item["spiller"] for item in session.get("spillere", [])]
    all_player_names = overview_players + [p for p in all_setup_players if p not in overview_players]

    round_finished = state["fullfort"]
    has_more_rounds = round_number < state["antall_runder"]
    own_group_finished = bool(holes) and holes[-1] in state["group_confirmed_hulls"]

    return {
        "live_rundeid": live_rundeid,
        "session": session,
        "state": state,
        "acting_player": acting_player,
        "round_number": round_number,
        "player_names": player_names,
        "score_df": score_df,
        "holes": holes,
        "base_key": base_key,
        "hole_key": hole_key,
        "hole": hole,
        "par": par,
        "show_all_key": show_all_key,
        "edit_all_scores_key": edit_all_scores_key,
        "overview_df": overview_df,
        "all_player_names": all_player_names,
        "round_finished": round_finished,
        "has_more_rounds": has_more_rounds,
        "own_group_finished": own_group_finished,
    }
