"""Sluttside for en fullført live-runde (siste runde i oppsettet): pallplass-visualisering + oversikt/alle slag."""

import streamlit as st

from ui.pages.live_runde_data import load_live_round_context
from ui.pages.live_runde_views import render_all_scores_editor, render_overview_panel

_MEDAL_COLORS = {1: "#caa85e", 2: "#b8c4bd", 3: "#a66a2c"}
_MEDAL_EMOJI = {1: "🥇", 2: "🥈", 3: "🥉"}
_PODIUM_ORDER = [2, 1, 3]

_PODIUM_STYLE = """
<style>
[data-testid="stHorizontalBlock"]:has(.podium-bar) {
    flex-wrap: nowrap !important;
    align-items: flex-end;
    gap: 6px;
}
[data-testid="stHorizontalBlock"]:has(.podium-bar) > div {
    min-width: 0 !important;
    width: auto !important;
    flex: 1 1 0 !important;
}
.podium-column { display:flex; flex-direction:column; align-items:center; justify-content:flex-end; gap:4px; }
.podium-emoji { font-size: clamp(1rem, 4.5vw, 1.6rem); line-height:1; }
.podium-name {
    font-weight:750; color:#20352d; text-align:center; width:100%;
    font-size: clamp(0.7rem, 3.2vw, 1rem); line-height:1.15; overflow-wrap:break-word;
}
.podium-bar {
    width:100%; display:flex; align-items:flex-start; justify-content:center;
    padding-top: clamp(4px, 1.5vw, 10px); border-radius:10px 10px 0 0;
    box-shadow: 0 2px 8px rgba(32, 53, 45, 0.12); box-sizing:border-box;
}
.podium-bar.place-1 { height: clamp(80px, 26vw, 170px); }
.podium-bar.place-2 { height: clamp(62px, 20vw, 125px); }
.podium-bar.place-3 { height: clamp(48px, 15vw, 95px); }
.podium-value { color:#ffffff; font-weight:750; font-size: clamp(0.8rem, 3.6vw, 1.3rem); }
</style>
"""


def _render_podium(overview_df) -> None:
    top_rows = overview_df.head(3).to_dict("records")
    if not top_rows:
        st.info("Ingen resultater å vise ennå.")
        return

    has_poeng = "poeng" in overview_df.columns
    st.markdown(_PODIUM_STYLE, unsafe_allow_html=True)
    placements = {int(row["plassering"]): row for row in top_rows}
    columns = st.columns(3, gap="small")
    for column, plassering in zip(columns, _PODIUM_ORDER):
        row = placements.get(plassering)
        with column:
            if row is None:
                continue
            color = _MEDAL_COLORS.get(plassering, "#b8cfc0")
            emoji = _MEDAL_EMOJI.get(plassering, "")
            spiller = str(row["spiller"])
            if has_poeng:
                poeng_value = float(row["poeng"])
                par_text = f"{poeng_value:g}p"
            else:
                spillers_par = int(row["spillers_par"])
                par_text = f"{spillers_par:+d}" if spillers_par != 0 else "E"
            st.markdown(
                f"""
                <div class="podium-column">
                    <div class="podium-emoji">{emoji}</div>
                    <div class="podium-name">{spiller}</div>
                    <div class="podium-bar place-{plassering}" style="background:{color};">
                        <span class="podium-value">{par_text}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def page():
    ctx = load_live_round_context()
    if ctx is None:
        return

    st.markdown('<h1 class="golf-page-title">Runde fullført 🏁</h1>', unsafe_allow_html=True)
    if st.button("Lukk", key=f"close_finished_round_{ctx['base_key']}"):
        st.session_state["live_runde_view"] = "oversikt"
        st.rerun()
    if ctx["state"].get("test_ind"):
        st.warning("TESTRUNDE – ingenting lagres")
    _render_podium(ctx["overview_df"])

    render_overview_panel(ctx["live_rundeid"], ctx["acting_player"], ctx["hole"], ctx["overview_df"])
    render_all_scores_editor(
        ctx["live_rundeid"],
        ctx["acting_player"],
        ctx["score_df"],
        ctx["all_player_names"],
        set(ctx["player_names"]),
        ctx["state"]["published_hulls"],
        ctx["state"]["par_by_hull"],
        editor_key=f"all_scores_summary_{ctx['base_key']}",
        editable=False,
    )
