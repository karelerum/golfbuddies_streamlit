import streamlit as st

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

    if ctx["round_finished"] and not ctx["has_more_rounds"]:
        st.session_state.pop(f"live_hole_{ctx['base_key']}", None)
        st.session_state.pop(ctx["show_all_key"], None)
        st.session_state.pop(ctx["edit_all_scores_key"], None)
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

    render_overview_panel(ctx["live_rundeid"], ctx["acting_player"], ctx["hole"], ctx["overview_df"])

    if show_all_scores:
        render_all_scores_mode(ctx)
    else:
        render_registration_mode(ctx)
