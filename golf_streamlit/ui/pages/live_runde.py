import html
import json

import streamlit as st

from aiapi.auth import get_logged_in_player
from aiapi.back_df_round import _is_admin_player
from aiapi.live_round import LiveRoundError, delete_live_round, get_active_live_rounds, is_test_session
import ui.pages.live_runde_slag as subpage_live_runde_slag
import ui.pages.live_runde_slag_slutt as subpage_live_runde_slag_slutt
import ui.pages.setup_live_runde as subpage_setup_live_runde


LIVE_ROUND_VIEWS = {
    "setup": subpage_setup_live_runde.page,
    "slag": subpage_live_runde_slag.page,
    "slag_slutt": subpage_live_runde_slag_slutt.page,
}

_ROUND_CARD_STYLE = """
<style>
:root {
    --gc-bg: #f3f5f3;
    --gc-surface: #ffffff;
    --gc-border: #dfe7e1;
    --gc-forest: #1f5d4a;
    --gc-forest-dark: #123d33;
    --gc-text: #1b2b26;
    --gc-muted: #526760;
    --gc-shadow: rgba(20, 41, 35, 0.08);
}

div[data-testid="stAppViewContainer"] {
    background: var(--gc-bg) !important;
}

div[class*="st-key-round_card_"] {
    background: var(--gc-surface) !important;
    border: 1px solid var(--gc-border) !important;
    border-radius: 12px !important;
    padding: 16px 18px 14px !important;
    margin: 0 0 14px 0 !important;
    box-shadow: 0 4px 14px var(--gc-shadow) !important;
}

.round-card-title {
    margin: 0 0 4px 0 !important;
    color: var(--gc-forest-dark) !important;
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    line-height: 1.2 !important;
}

.round-card-meta {
    margin: 0 0 8px 0 !important;
    color: var(--gc-muted) !important;
    font-size: 0.76rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}

.round-card-groups {
    margin: 0 0 10px 0 !important;
    color: var(--gc-text) !important;
    font-size: 0.92rem !important;
    line-height: 1.5 !important;
}

.round-card-divider {
    border-bottom: 1px solid #edf2ee;
    margin: 10px 0 12px 0;
}

div[class*="st-key-round_card_"] button[data-testid="stBaseButton-primary"] {
    background: #1f5d4a !important;
    border: 1px solid #173f35 !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
}

div[class*="st-key-round_card_"] button[data-testid="stBaseButton-secondary"] {
    background: #f0f4f1 !important;
    border: 1px solid #cfe1d2 !important;
    color: var(--gc-forest-dark) !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
}

div[class*="st-key-round_card_"] button[data-testid="stBaseButton-secondary"]:hover {
    background: #e2ede5 !important;
}
</style>
"""


def _round_group_lines(spillere_raw) -> list[str]:
    """Format 'Gruppe N: spiller1 | spiller2' lines from the raw (JSON) spillere column."""
    try:
        spillere = json.loads(spillere_raw) if isinstance(spillere_raw, str) else (spillere_raw or [])
    except (TypeError, ValueError):
        spillere = []
    groups: dict[int, list[str]] = {}
    for player in spillere:
        gruppe = int(player.get("gruppe", 1))
        groups.setdefault(gruppe, []).append(str(player.get("spiller", "")))
    return [f"Gruppe {gruppe}: {' | '.join(names)}" for gruppe, names in sorted(groups.items()) if names]


def _render_round_card(round_row: dict, is_admin: bool) -> None:
    live_rundeid = str(round_row["live_rundeid"])
    title = str(round_row.get("tittel") or f"Runde {round_row['runde']}")
    group_lines = _round_group_lines(round_row.get("spillere"))
    groups_html = "<br>".join(html.escape(line) for line in group_lines) or "<span>Ingen grupper satt</span>"
    test_html = " | TEST" if is_test_session(round_row) else ""

    with st.container(key=f"round_card_{live_rundeid}"):
        st.markdown(
            f'<p class="round-card-title">{html.escape(title)}</p>'
            f'<p class="round-card-meta">Bane: {html.escape(str(round_row["bane"]))} | Runder: {html.escape(str(round_row.get("antall_runder", 1)))}{test_html}</p>'
            f'<p class="round-card-groups">{groups_html}</p>'
            f'<div class="round-card-divider"></div>',
            unsafe_allow_html=True,
        )

        if is_admin:
            c1, c2, c3, _ = st.columns([3, 1, 1, 3], vertical_alignment="center")
        else:
            c1, _ = st.columns([3, 5], vertical_alignment="center")

        with c1:
            if st.button("Åpne runde", key=f"open_live_round_{live_rundeid}", type="primary", use_container_width=True):
                st.session_state.live_session_id = live_rundeid
                st.session_state.live_runde_view = "slag"
                st.session_state.live_open_next_hole_for = live_rundeid
                st.rerun()

        if is_admin:
            with c2:
                if st.button(":material/edit:", key=f"edit_live_round_{live_rundeid}", help="Rediger live-runde", use_container_width=True):
                    st.session_state.live_edit_rundeid = live_rundeid
                    st.session_state.live_runde_view = "setup"
                    st.rerun()
            with c3:
                if st.button(":material/delete:", key=f"delete_live_round_{live_rundeid}", help="Slett live-runde", use_container_width=True):
                    try:
                        delete_live_round(live_rundeid)
                    except LiveRoundError as exc:
                        st.error(str(exc))
                    else:
                        st.rerun()


def _show_round_cards(is_admin: bool) -> None:
    active_rounds_df = get_active_live_rounds()
    if active_rounds_df.empty:
        st.info("Det er ingen aktive live-runder akkurat nå.")
        return

    st.markdown(_ROUND_CARD_STYLE, unsafe_allow_html=True)
    for _, round_row in active_rounds_df.reset_index(drop=True).iterrows():
        _render_round_card(round_row.to_dict(), is_admin)


def page():
    current_player = get_logged_in_player()
    if not current_player:
        st.warning("Du må være logget inn for å se live-runder.")
        return

    if st.session_state.get("live_runde_view") not in LIVE_ROUND_VIEWS:
        st.session_state.live_runde_view = "oversikt"

    if st.session_state.live_runde_view in LIVE_ROUND_VIEWS:
        LIVE_ROUND_VIEWS[st.session_state.live_runde_view]()
        return

    is_admin = _is_admin_player(current_player)
    if is_admin:
        admin_actions = st.container(horizontal=True)
        if admin_actions.button("Lag ny live runde", type="primary"):
            st.session_state.pop("live_edit_rundeid", None)
            st.session_state.live_runde_view = "setup"
            st.rerun()

    _show_round_cards(is_admin)