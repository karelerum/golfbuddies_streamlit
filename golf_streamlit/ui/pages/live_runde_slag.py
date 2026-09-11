import pandas as pd
import streamlit as st

from aiapi.live_round import LiveRoundError, finalize_live_round_session, get_live_hole_points
from config.constants import LIVE_ROUND_TYPE_6P
from ui.pages.live_runde_data import load_live_round_context
from ui.pages.live_runde_views import (
    render_all_scores_mode,
    render_overview_panel,
    render_registration_mode,
    render_top_toolbar,
    render_waiting_for_other_group_notice,
)


def page():
    """Row 1: tittel+knapp -> Oversikttabell -> se_Velghull -> slag_pr_spiller_pr_runde_visning + regiter_knapper."""
    ctx = load_live_round_context()
    if ctx is None:
        return

    is_test = bool(ctx["state"].get("test_ind"))
    if is_test:
        st.warning("TESTRUNDE – ingenting lagres")

    if ctx["round_finished"] and not ctx["has_more_rounds"]:
        finalization_error_key = f"live_finalization_error_{ctx['live_rundeid']}"
        if finalization_error_key in st.session_state:
            st.error(st.session_state[finalization_error_key])
            if st.button("Prøv igjen", key=f"retry_finalization_{ctx['base_key']}"):
                st.session_state.pop(finalization_error_key, None)
                st.rerun()
            return
        try:
            with st.spinner("Avslutter testrunde ..." if is_test else "Lagrer ferdig runde ..."):
                finalize_live_round_session(str(ctx["live_rundeid"]), str(ctx["acting_player"]))
        except LiveRoundError as exc:
            st.session_state[finalization_error_key] = str(exc)
            st.rerun()
            return

        st.session_state.pop(f"live_hole_{ctx['base_key']}", None)
        st.session_state.pop(ctx["show_all_key"], None)
        st.session_state.pop(ctx["edit_all_scores_key"], None)
        st.session_state.pop(finalization_error_key, None)
        st.session_state["live_runde_view"] = "slag_slutt"
        st.rerun()
        return

    show_all_scores = True if ctx["round_finished"] else st.session_state[ctx["show_all_key"]]
    render_top_toolbar(
        ctx["session"],
        ctx["live_rundeid"],
        ctx["acting_player"],
        ctx["round_number"],
        ctx["show_all_key"],
        show_all_scores,
        toggle_key=f"toggle_all_scores_{ctx['base_key']}",
        base_key=ctx["base_key"],
        round_finished=ctx["round_finished"],
        has_more_rounds=ctx["has_more_rounds"],
    )

    if ctx["own_group_finished"] and not ctx["round_finished"]:
        render_waiting_for_other_group_notice()

    previous_hole_points = None
    previous_hole_scores = None
    previous_points_hole = None
    previous_scores_hole = None
    if ctx["session"].get("type_runde") == LIVE_ROUND_TYPE_6P and show_all_scores:
        score_df = ctx["score_df"].copy()
        score_df["hull"] = pd.to_numeric(score_df["hull"], errors="coerce")
        published_hulls = ctx["state"]["published_hulls"]
        previous_points_hole = max(published_hulls) if published_hulls else None
        previous_scores_hole = previous_points_hole
        if previous_scores_hole is not None:
            previous_row = score_df.loc[score_df["hull"].astype(int) == previous_scores_hole].iloc[0]
            previous_hole_scores = {
                player: int(previous_row.get(player, 0)) if pd.notna(previous_row.get(player)) else 0
                for player in ctx["all_player_names"]
            }
        if previous_points_hole is not None:
            hole_points = get_live_hole_points(
                ctx["score_df"], ctx["state"]["par_by_hull"], published_hulls, ctx["all_player_names"]
            )
            previous_hole_points = {
                player: float(hole_points.get((previous_points_hole, player), 0.0)) for player in ctx["all_player_names"]
            }

    render_overview_panel(
        ctx["live_rundeid"],
        ctx["acting_player"],
        ctx["hole"],
        ctx["overview_df"],
        show_all_scores=show_all_scores,
        previous_hole_points=previous_hole_points,
        previous_hole_scores=previous_hole_scores,
        previous_points_hole=previous_points_hole,
        previous_scores_hole=previous_scores_hole,
    )

    if show_all_scores:
        render_all_scores_mode(ctx)
    else:
        render_registration_mode(ctx)
