"""Rendering functions for the Live Runde Slag page: one function per UI block, composed by live_runde_slag.page()."""

import html

import pandas as pd
import streamlit as st

from aiapi.live_round import LiveRoundError, advance_to_next_live_round, confirm_live_hole, get_live_hole_points, save_live_hole_scores, save_live_score
from config.constants import LIVE_ROUND_TYPE_6P
from ui.components.html_visuals import all_scores_table, live_overview_table, register_btns
from ui.pages.live_runde_data import _build_all_scores_rows, _build_overview_rows

TITLE_MAX_FONT_REM = 1.4
TITLE_MIN_FONT_REM = 0.95
TITLE_SHRINK_START_CHARS = 20
TITLE_SHRINK_END_CHARS = 55


def _dynamic_title_font_size(text: str) -> str:
    """Scale font-size down as the title text gets longer, so it shrinks instead of getting cut off with an ellipsis."""
    length = len(text)
    if length <= TITLE_SHRINK_START_CHARS:
        return f"{TITLE_MAX_FONT_REM}rem"
    if length >= TITLE_SHRINK_END_CHARS:
        return f"{TITLE_MIN_FONT_REM}rem"
    ratio = (length - TITLE_SHRINK_START_CHARS) / (TITLE_SHRINK_END_CHARS - TITLE_SHRINK_START_CHARS)
    size = TITLE_MAX_FONT_REM - ratio * (TITLE_MAX_FONT_REM - TITLE_MIN_FONT_REM)
    return f"{size:.2f}rem"


def render_top_toolbar(
    session: dict,
    live_rundeid: str,
    current_player: str,
    round_number: int,
    show_all_key: str,
    show_all_scores: bool,
    toggle_key: str,
    base_key: str,
    round_finished: bool,
    has_more_rounds: bool,
) -> None:
    """Row 1: tittel + Alle slag/Registrer slag-knapp (eller Hopp til runde N+1 når runden er fullført)."""
    with st.container(horizontal=True, vertical_alignment="center"):
        if st.button(
            ":material/arrow_back:",
            key=f"back_to_live_rounds_{base_key}",
            help="Tilbake til live-runder",
            type="secondary",
        ):
            st.session_state["live_runde_view"] = "oversikt"
            st.rerun()

        title_text = f"{session.get('tittel') or 'Live Runde'} - Runde {round_number}"
        safe_title_text = html.escape(title_text)
        title_font_size = _dynamic_title_font_size(title_text)
        st.markdown(
            f'<h1 class="golf-page-title" style="font-size:{title_font_size};">{safe_title_text}</h1>',
            unsafe_allow_html=True,
        )
        if round_finished and has_more_rounds:
            if st.button(f"Hopp til runde {round_number + 1}", key=toggle_key):
                try:
                    advance_to_next_live_round(str(live_rundeid), str(current_player))
                except LiveRoundError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.pop(f"live_hole_{base_key}", None)
                    st.session_state.pop(show_all_key, None)
                    st.session_state.pop(f"live_edit_all_scores_{base_key}", None)
                    st.rerun()
        elif not round_finished:
            if st.button("Registrer slag" if show_all_scores else "Alle slag", key=toggle_key):
                st.session_state[show_all_key] = not show_all_scores
                st.rerun()


def render_overview_panel(
    live_rundeid: str,
    current_player: str,
    hole: int,
    overview_df: pd.DataFrame,
) -> None:
    """Oversikttabell: plassering/par/slag for alle spillere."""
    live_overview_table(_build_overview_rows(overview_df), key=f"live_overview_{live_rundeid}_{current_player}_{hole}")


def render_waiting_for_other_group_notice() -> None:
    """Vises når egen gruppe har fullført siste hull, men den andre gruppen ikke er ferdig ennå."""
    st.caption("Dere er ferdig! Venter på at den andre gruppen fullfører runden.")


@st.dialog("Velg hull")
def _show_hole_picker(
    hole_key: str,
    holes: list[int],
    confirmed_holes: set[int],
) -> None:
    for selected_hole in sorted(holes):
        label = f"Hull {selected_hole} ✅" if selected_hole in confirmed_holes else f"Hull {selected_hole}"
        if st.button(
            label,
            key=f"hole_picker_{hole_key}_{selected_hole}",
            type="primary" if st.session_state.get(hole_key) == selected_hole else "secondary",
            use_container_width=True,
        ):
            st.session_state[hole_key] = selected_hole
            st.rerun()


def render_hole_navigation(
    live_rundeid: str,
    current_player: str,
    hole_key: str,
    holes: list[int],
    hole: int,
    par: int,
    show_all_key: str,
    confirmed_holes: set[int],
) -> None:
    """se_Velghull: forrige/neste hull; siste hull tilbyr å fullføre runden i stedet for å gå videre."""
    is_last_hole = hole == holes[-1]
    with st.container(horizontal=True, vertical_alignment="center"):
        if st.button(":material/arrow_back:", key=f"previous_hole_{hole_key}", disabled=hole == holes[0], help="Forrige hull", width="stretch"):
            st.session_state[hole_key] = holes[holes.index(hole) - 1]
            st.rerun()
        hole_label = f"Hull {hole} · Par {par}" + (" ✅" if hole in confirmed_holes else "")
        if st.button(
            hole_label,
            key=f"select_hole_{hole_key}",
            help="Velg hull",
            width="stretch",
        ):
            _show_hole_picker(
                hole_key,
                holes,
                confirmed_holes,
            )
        if is_last_hole:
            if st.button("Fullfør runde", key=f"finish_round_{hole_key}", help="Bekreft siste hull for egen gruppe", width="stretch"):
                try:
                    with st.spinner("Fullfører runde og synkroniserer med Sheets ..."):
                        confirm_live_hole(str(live_rundeid), str(current_player), hole)
                except LiveRoundError as exc:
                    st.error(str(exc))
                else:
                    st.session_state[show_all_key] = True
                    st.rerun()
        else:
            if st.button(":material/arrow_forward:", key=f"next_hole_{hole_key}", help="Bekreft og gå til neste hull", width="stretch"):
                try:
                    confirm_live_hole(str(live_rundeid), str(current_player), hole)
                except LiveRoundError as exc:
                    st.error(str(exc))
                else:
                    st.session_state[hole_key] = holes[holes.index(hole) + 1]
                    st.rerun()


def render_all_scores_editor(
    live_rundeid: str,
    current_player: str,
    score_df: pd.DataFrame,
    all_player_names: list[str],
    own_group_players: set[str],
    published_hulls: set[int],
    par_by_hull: dict[int, int],
    editor_key: str,
    editable: bool,
    hole_points: dict[tuple[int, str], float] | None = None,
) -> None:
    """Editable Hull x spiller table for all players; masks unpublished opposing group scores and saves each changed cell for own group.
    When `hole_points` is given (6P Poeng-visning), cells show P6-points instead of slag and are always read-only."""
    rows = _build_all_scores_rows(
        score_df,
        all_player_names,
        par_by_hull,
        own_group_players=own_group_players,
        published_hulls=published_hulls,
        hole_points=hole_points,
    )
    editable = editable and hole_points is None
    result = all_scores_table(rows, all_player_names, key=editor_key, editable=editable)
    if not isinstance(result, dict):
        return

    event_id = result.get("event_id")
    handled_event_key = f"{editor_key}_handled_event"
    if event_id is not None and st.session_state.get(handled_event_key) == event_id:
        return

    player_name = result.get("player")
    hull_number = result.get("hull")
    score_value = result.get("score")
    if player_name not in all_player_names or hull_number is None or score_value is None:
        return
    try:
        save_live_score(str(live_rundeid), str(current_player), str(player_name), int(hull_number), int(score_value))
    except (TypeError, ValueError):
        st.error("Slag må være et heltall.")
    except LiveRoundError as exc:
        st.error(str(exc))
    else:
        if event_id is not None:
            st.session_state[handled_event_key] = event_id
        st.rerun()


def _all_scores_registered(player_names: list[str], scores: dict[str, int]) -> bool:
    return bool(player_names) and all(scores.get(player_name) is not None for player_name in player_names)


def render_registration_keypad(
    live_rundeid: str,
    current_player: str,
    score_df: pd.DataFrame,
    player_names: list[str],
    hole: int,
    par: int,
    component_key: str,
    synced_key: str,
    hole_key: str,
    holes: list[int],
    show_all_key: str,
) -> None:
    """slag_pr_spiller_pr_runde_visning + regiter_knapper: begge tegnes av samme register_btns-komponent (én JS-widget)."""
    initial_scores = {}
    for player_name in player_names:
        saved_score = score_df.loc[score_df["hull"].astype(int).eq(hole), player_name].iloc[0]
        if not pd.isna(saved_score):
            initial_scores[player_name] = int(saved_score)

    if synced_key not in st.session_state:
        st.session_state[synced_key] = dict(initial_scores)

    result = register_btns(par=par, key=component_key, spillere=player_names, scores=initial_scores)
    if isinstance(result, dict):
        submitted_scores = result.get("scores", {})
        if not _all_scores_registered(player_names, submitted_scores):
            return
        try:
            save_live_hole_scores(str(live_rundeid), str(current_player), hole, submitted_scores)
            confirm_live_hole(str(live_rundeid), str(current_player), hole)
        except LiveRoundError as exc:
            st.error(str(exc))
            return
        if hole == holes[-1]:
            st.session_state[show_all_key] = True
        else:
            st.session_state[hole_key] = holes[holes.index(hole) + 1]
        st.session_state.pop(synced_key, None)
        st.rerun()


def render_registration_mode(ctx: dict) -> None:
    """se_Velghull + slag_pr_spiller_pr_runde_visning + regiter_knapper for aktiv gruppe/hull."""
    render_hole_navigation(
        ctx["live_rundeid"],
        ctx["acting_player"],
        ctx["hole_key"],
        ctx["holes"],
        ctx["hole"],
        ctx["par"],
        ctx["show_all_key"],
        ctx["state"]["group_confirmed_hulls"],
    )
    component_key = f"register_btns_{ctx['base_key']}_{ctx['hole']}"
    render_registration_keypad(
        ctx["live_rundeid"],
        ctx["acting_player"],
        ctx["score_df"],
        ctx["player_names"],
        ctx["hole"],
        ctx["par"],
        component_key,
        synced_key=f"{component_key}_synced",
        hole_key=ctx["hole_key"],
        holes=ctx["holes"],
        show_all_key=ctx["show_all_key"],
    )


def render_all_scores_mode(ctx: dict) -> None:
    """Alternativ visning: redigerbar Hull x spiller-tabell for alle, i stedet for hull-for-hull-registrering."""
    edit_all_scores_key = ctx["edit_all_scores_key"]
    editing_all_scores = st.session_state[edit_all_scores_key]
    is_6p = ctx["session"].get("type_runde") == LIVE_ROUND_TYPE_6P
    points_mode_key = f"live_points_mode_{ctx['base_key']}"
    if points_mode_key not in st.session_state:
        st.session_state[points_mode_key] = False
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown('<p class="golf-section-label">Alle slag</p>', unsafe_allow_html=True)
        if is_6p:
            points_mode = st.session_state[points_mode_key]
            if st.button("Vis slag" if points_mode else "Vis poeng", key=f"toggle_points_mode_{ctx['base_key']}"):
                st.session_state[points_mode_key] = not points_mode
                st.rerun()
        if st.button(
            ":material/done:" if editing_all_scores else ":material/edit:",
            key=f"toggle_edit_all_scores_{ctx['base_key']}",
            help="Ferdig" if editing_all_scores else "Rediger alle slag",
        ):
            st.session_state[edit_all_scores_key] = not editing_all_scores
            st.rerun()
    hole_points = None
    if is_6p and st.session_state[points_mode_key]:
        hole_points = get_live_hole_points(
            ctx["score_df"], ctx["state"]["par_by_hull"], ctx["state"]["published_hulls"], ctx["all_player_names"]
        )
    render_all_scores_editor(
        ctx["live_rundeid"],
        ctx["acting_player"],
        ctx["score_df"],
        ctx["all_player_names"],
        set(ctx["player_names"]),
        ctx["state"]["published_hulls"],
        ctx["state"]["par_by_hull"],
        editor_key=f"all_scores_editor_{ctx['base_key']}",
        editable=editing_all_scores,
        hole_points=hole_points,
    )
