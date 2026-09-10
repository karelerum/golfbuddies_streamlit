import os

import streamlit as st

from aiapi.player_views import PLAYER_TOURNAMENT_FILTERS, filter_player_badges_by_tournament_type
from src import my_dfs

_BADGES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "badges")
_COLS = 3
_HOVED_FILNAVN = {"hole_in_one.png", "eagle.png"}


def _available_badge_files() -> set[str]:
    try:
        return {f for f in os.listdir(_BADGES_DIR) if os.path.isfile(os.path.join(_BADGES_DIR, f))}
    except OSError:
        return set()


def _badge_description(badge: dict) -> str:
    for key in ("forklaring", "beskrivelse", "description"):
        value = badge.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _render_badge_info(description: str, key: str) -> None:
    if st.button("Info", key=key, use_container_width=True):
        st.info(description or "Ingen forklaring er tilgjengelig for dette merket.")


def page():
    current_player = st.session_state.get("innlogget_spiller")
    if not current_player:
        st.warning("Du må være logget inn for å se merker.")
        return

    st.title("Merker")

    show_badge_info = st.toggle(
        "Vis info-knapper",
        value=False,
        key="player_badges_show_info",
    )

    tournament_filter_label = st.segmented_control(
        "Velg sesong",
        options=list(PLAYER_TOURNAMENT_FILTERS),
        selection_mode="single",
        default="Begge",
        label_visibility="collapsed",
        key="player_badges_tournament_filter",
    ) or "Begge"

    spillermerker_df = my_dfs.get_spillermerker_df()
    if spillermerker_df is None or spillermerker_df.empty:
        st.info("Ingen merker funnet.")
        return

    # Filter on logged-in player
    player_df = spillermerker_df.loc[
        spillermerker_df["spiller"].astype(str).str.strip().eq(str(current_player).strip())
    ].copy()
    player_df = filter_player_badges_by_tournament_type(
        player_df,
        my_dfs.get_tournament_info_df(),
        tournament_filter_label,
    )

    if player_df.empty:
        st.info("Du har ingen merker ennå.")
        return

    # Count occurrences before deduplicating
    counts = player_df.groupby("filnavn")["filnavn"].transform("count")
    player_df = player_df.copy()
    player_df["_count"] = counts
    player_df = player_df.drop_duplicates(subset=["filnavn"])

    # Join with merker to get prioritet for sorting
    merker_df = my_dfs.get_merker_df()
    if merker_df is not None and not merker_df.empty and "merke_id" in merker_df.columns:
        badge_meta_cols = ["merke_id", "prioritet"]
        if "forklaring" in merker_df.columns:
            badge_meta_cols.append("forklaring")
        badge_meta_cols = [column for column in dict.fromkeys(badge_meta_cols) if column in merker_df.columns]
        if badge_meta_cols:
            prio_df = merker_df[badge_meta_cols].drop_duplicates(subset=["merke_id"])
            player_df = player_df.drop(columns=["forklaring"], errors="ignore").merge(
                prio_df,
                on="merke_id",
                how="left",
            )
    if "prioritet" not in player_df.columns:
        player_df["prioritet"] = 0
    if "forklaring" not in player_df.columns:
        player_df["forklaring"] = ""

    player_df["prioritet"] = player_df["prioritet"].fillna(0)
    player_df = player_df.sort_values(
        ["prioritet", "filnavn"], ascending=[False, True]
    ).reset_index(drop=True)

    available_files = _available_badge_files()

    is_hoved = (
        player_df["vinner_innen"].isin(["turnering", "totalt", "total"])
        | player_df["filnavn"].isin(_HOVED_FILNAVN)
    )
    hoved_badges = player_df.loc[
        is_hoved,
        ["filnavn", "visningsnavn", "_count", "forklaring"],
    ].to_dict("records")
    runde_badges = player_df.loc[
        ~is_hoved & ~player_df["filnavn"].isin(_HOVED_FILNAVN),
        ["filnavn", "visningsnavn", "_count", "forklaring"],
    ].to_dict("records")

    def _render_grid(badges: list[dict], grid_name: str, n_cols: int = _COLS) -> None:
        if not badges:
            st.caption("Ingen merker her ennå.")
            return
        st.markdown(
            f"""
            <style>
            .st-key-badge-grid-{grid_name} [data-testid="stHorizontalBlock"] {{
                flex-direction: row !important;
                flex-wrap: nowrap !important;
            }}
            .st-key-badge-grid-{grid_name} [data-testid="stColumn"] {{
                min-width: 0 !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key=f"badge-grid-{grid_name}"):
            cols = st.columns(n_cols, gap="small")
        for i, badge in enumerate(badges):
            filnavn = str(badge.get("filnavn", ""))
            count = int(badge.get("_count", 1))
            visningsnavn = str(badge.get("visningsnavn", ""))
            description = _badge_description(badge)
            label = f"{visningsnavn} ×{count}" if count > 1 else visningsnavn
            with cols[i % n_cols]:
                if filnavn in available_files:
                    st.image(os.path.join(_BADGES_DIR, filnavn), width="stretch")
                else:
                    st.markdown("fil ikke funnet.")
                st.caption(label)
                if show_badge_info:
                    _render_badge_info(description, f"badge_info_{grid_name}_{i}_{filnavn}")

    st.subheader("Hovedmerker")
    _render_grid(hoved_badges, "hoved")

    st.subheader("Rundemerker")
    _render_grid(runde_badges, "runde")
