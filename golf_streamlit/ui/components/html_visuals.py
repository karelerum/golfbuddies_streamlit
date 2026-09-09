from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from ui.components.badge_animation import get_badge_data_uris

_REGISTER_BTNS_DIR = Path(__file__).parent / "register_btns_frontend"
_LIVE_OVERVIEW_DIR = Path(__file__).parent / "live_overview_frontend"
_ALL_SCORES_DIR = Path(__file__).parent / "all_scores_frontend"
_register_btns_component = components.declare_component("register_btns", path=str(_REGISTER_BTNS_DIR))
_live_overview_component = components.declare_component("live_overview_table", path=str(_LIVE_OVERVIEW_DIR))
_all_scores_component = components.declare_component("all_scores_table", path=str(_ALL_SCORES_DIR))


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


def register_number_btn(value: str, label: str, key: str, bredde: int = 104) -> None:
    """Render a square visual number-button prototype for the live score keypad."""
    bredde = max(64, min(int(bredde), 104))
    value_size = max(28, round(bredde * 0.4))
    st.markdown(
        f"""
        <div id="{key}" style="
            width: min(100%, {bredde}px);
            aspect-ratio: 1;
            margin: 4px;
            padding: 12px;
            border: 1px solid #b8cfc0;
            border-radius: 6px;
            background: #e7f0e8;
            color: #20352d;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 8px;
            text-align: center;
            box-sizing: border-box;
        ">
            <div style="font-size: {value_size}px; font-weight: 700; line-height: 1;">{value}</div>
            <div style="font-size: 13px; line-height: 1.25;">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def register_tekst_btn(tekst: str, key: str, bredde: int = 104) -> None:
    """Render a square visual text-button prototype for live registration controls."""
    bredde = max(64, min(int(bredde), 104))
    st.markdown(
        f"""
        <div id="{key}" style="
            width: min(100%, {bredde}px);
            aspect-ratio: 1;
            margin: 4px;
            padding: 12px;
            border: 1px solid #b8cfc0;
            border-radius: 6px;
            background: #e7f0e8;
            color: #20352d;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: 15px;
            font-weight: 600;
            line-height: 1.25;
            box-sizing: border-box;
        ">
            {tekst}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_test_card(title: str, body: str) -> None:
    """Render a simple framed component for visual experiments."""
    with st.container(border=True):
        st.subheader(title)
        st.write(body)
