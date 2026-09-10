from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from ui.components.badge_animation import get_badge_data_uris

_REGISTER_BTNS_DIR = Path(__file__).parent / "register_btns_frontend"
_LIVE_OVERVIEW_DIR = Path(__file__).parent / "live_overview_frontend"
_ALL_SCORES_DIR = Path(__file__).parent / "all_scores_frontend"
_LIVE_SESSION_DIR = Path(__file__).parent / "live_session_frontend"
_COUNTDOWN_TIMER_DIR = Path(__file__).parent / "countdown_timer_frontend"
_register_btns_component = components.declare_component("register_btns", path=str(_REGISTER_BTNS_DIR))
_live_overview_component = components.declare_component("live_overview_table", path=str(_LIVE_OVERVIEW_DIR))
_all_scores_component = components.declare_component("all_scores_table", path=str(_ALL_SCORES_DIR))
_live_session_component = components.declare_component("live_round_session", path=str(_LIVE_SESSION_DIR))
_countdown_timer_component = components.declare_component("countdown_timer", path=str(_COUNTDOWN_TIMER_DIR))


def register_btns(
    par: int,
    key: str,
    spillere: list[str] | None = None,
    scores: dict[str, int] | None = None,
    hole: int | None = None,
) -> dict | str | None:
    """Render the score keypad, optionally with a player name/score table above it.

    Without `spillere`, returns the clicked score as a string ("1".."11").
    With `spillere`, clicking a name selects who scores are registered for, and
    clicking a score assigns it to the selected player, then advances selection
    to the next player (stays on the last player). Returns
    {"scores": {navn: slag}, "current_player": navn} after each score click.
    `scores` seeds already-registered values on first load (e.g. when reopening
    a hole); use a `key` that changes per hole so the seed applies correctly.
    Mer/Tilbake only toggles the visible grid locally and is never returned.
    Button size is responsive via CSS grid (max 104px per button, 3 per row).
    A birdie/eagle/hole-in-one click pops up a badge animation inside the component itself.
    """
    return _register_btns_component(
        par=int(par), hole=hole, spillere=spillere or [], scores=scores or {}, badges=get_badge_data_uris(), key=key, default=None
    )


def live_overview_table(rows: list[dict], key: str) -> dict | None:
    """Render a compact read-only live round overview table."""
    return _live_overview_component(rows=rows, key=key, default=None)


def all_scores_table(rows: list[dict], players: list[str], key: str, editable: bool = False) -> dict | None:
    """Render a read-only or editable live score grid and return changed cells."""
    return _all_scores_component(rows=rows, players=players, editable=editable, key=key, default=None)


def live_round_session(payload: dict | None, clear: bool = False) -> dict | None:
    """Synchronize the active Live Runde with browser session storage."""
    return _live_session_component(payload=payload, clear=clear, key="live_round_session", default=None)


def render_test_card(title: str, body: str) -> None:
    """Render a simple framed component for visual experiments."""
    with st.container(border=True):
        st.subheader(title)
        st.write(body)


def render_countdown_timer(deadline: datetime, label: str = "") -> None:
    """Render a live client-side countdown (days/timer/min/sek) with a trophy icon and a close (x) button.

    Uses a bidirectional custom component (not `components.html`) so the close click can tell Python to
    stop rendering it entirely — a plain `components.html` iframe always reserves its fixed `height`,
    even once hidden client-side, leaving dead space. Closing only affects this session; it reappears on
    the next full app open/refresh.
    """
    closed_key = "countdown_timer_closed"
    placeholder = st.empty()
    if st.session_state.get(closed_key):
        placeholder.empty()
        return

    with placeholder.container():
        result = _countdown_timer_component(
            year=deadline.year,
            month=deadline.month,
            day=deadline.day,
            hour=deadline.hour,
            minute=deadline.minute,
            label=label,
            key="countdown_timer",
            default=None,
        )
    if isinstance(result, dict) and result.get("action") == "close":
        st.session_state[closed_key] = True
        st.rerun()
