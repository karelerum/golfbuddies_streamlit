import altair as alt
import os
import pandas as pd
import streamlit as st

from aiapi.auth import get_logged_in_player
from aiapi.home_views import (
    build_home_chart_df,
    build_round_selector_options,
    format_numeric_value,
    get_home_round_options,
    prepare_course_chart_df,
    prepare_home_tournaments,
)
from src import my_dfs
from config.design_tokens import CHART_COLORS


VALUE_OPTIONS = ["P6", "Slag"]
FUN_OPTIONS = ["Birdie og sånn", "Gruppen pr runde", "Pall-plasser"]
_BADGES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "badges")
_ROUND_BADGE_COLUMNS = 4


def _identifier_mask(values: pd.Series, identifier: str) -> pd.Series:
    normalized_identifier = str(identifier).strip()
    direct_matches = values.astype(str).str.strip().eq(normalized_identifier)
    numeric_identifier = pd.to_numeric(normalized_identifier, errors="coerce")
    if pd.isna(numeric_identifier):
        return direct_matches
    numeric_matches = pd.to_numeric(values, errors="coerce").eq(numeric_identifier)
    return direct_matches | numeric_matches


def _render_round_badges(spillermerker_df: pd.DataFrame | None, current_player: str, rundeid: str) -> None:
    if spillermerker_df is None or spillermerker_df.empty:
        return

    required_columns = {"spiller", "rundeid", "vinner_innen", "filnavn", "visningsnavn"}
    if not required_columns.issubset(spillermerker_df.columns):
        return

    badges = spillermerker_df.loc[
        spillermerker_df["spiller"].astype(str).str.strip().eq(str(current_player).strip())
        & _identifier_mask(spillermerker_df["rundeid"], str(rundeid))
        & spillermerker_df["vinner_innen"].astype(str).str.strip().str.lower().eq("runde")
    ].drop_duplicates(subset=["filnavn"])
    badges = badges.loc[badges["filnavn"].astype(str).map(
        lambda filename: os.path.isfile(os.path.join(_BADGES_DIR, filename))
    )]

    if badges.empty:
        return

    st.markdown(
        """
        <style>
        div[class*="st-key-home-round-badge-grid"] [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
        }
        div[class*="st-key-home-round-badge-grid"] [data-testid="stColumn"] {
            min-width: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    badge_records = badges[["filnavn", "visningsnavn"]].to_dict("records")
    with st.container(key="home-round-badge-grid"):
        for row_start in range(0, len(badge_records), _ROUND_BADGE_COLUMNS):
            badge_columns = st.columns(_ROUND_BADGE_COLUMNS, gap="small")
            for column, badge in zip(badge_columns, badge_records[row_start:row_start + _ROUND_BADGE_COLUMNS]):
                with column:
                    filename = str(badge["filnavn"])
                    st.image(os.path.join(_BADGES_DIR, filename), width="stretch")
                    st.caption(str(badge["visningsnavn"]))


def page():
    st.subheader("Hjem")
    current_player = get_logged_in_player()

    def format_numeric_df(df):
        return df.style.format(format_numeric_value, subset=df.select_dtypes(include="number").columns)

    result_df = my_dfs.get_result_df()
    tournament_df = my_dfs.get_tournament_info_df()
    round_info_df = my_dfs.get_round_info_df()

    tournament_df, round_info_df = prepare_home_tournaments(result_df, tournament_df, round_info_df)

    if tournament_df.empty or round_info_df.empty:
        st.write("Fant ingen turneringsdata.")
        return

    tournament_name = st.selectbox("Velg sesong:", options=tournament_df["turneringsnavn"].tolist(), index=0)
    tournament_id = str(tournament_df.loc[tournament_df["turneringsnavn"] == tournament_name, "turneringsid"].iloc[0])

    tab_oversikt, tab_annet = st.tabs(["Turneringsoversikt", "Annet gøy"])

    with tab_oversikt:
        valgt_verdi = st.segmented_control(
            "Velg verdi",
            options=VALUE_OPTIONS,
            selection_mode="single",
            default="P6",
            label_visibility="collapsed",
            key="home_value_overview",
        ) or "P6"

        tournament_round_info_df, round_label_map = get_home_round_options(round_info_df, result_df, tournament_id)

        pivot_df = my_dfs.resultat_runde_pivot(tournament_id, valgt_verdi).rename(columns=round_label_map)

        st.dataframe(
            format_numeric_df(pivot_df),
            width="stretch",
        )

        chart_df, value_column = build_home_chart_df(
            result_df,
            round_info_df,
            tournament_id,
            valgt_verdi,
            my_dfs.RESULT_VALUE_ALIASES,
        )
        chart_df = chart_df.copy()
        chart_df["is_current_player"] = chart_df["spiller"].eq(current_player)

        akkumulert_ind = st.toggle("Vis akkumulert", value=False)
        if akkumulert_ind:
            chart_df[value_column] = chart_df.sort_values(["spiller", "runde"]).groupby("spiller")[value_column].cumsum()

        player_order = chart_df.groupby("spiller")[value_column].sum().sort_values(ascending=value_column == "slag").index.tolist()
        y_min = chart_df[value_column].min()
        y_max = chart_df[value_column].max()
        padding = 0 if pd.isna(y_min) or pd.isna(y_max) else max((y_max - y_min) * 0.1, 1)
        base_chart = alt.Chart(chart_df).encode(
            x=alt.X("runde:O", title="Runde", sort="ascending", axis=alt.Axis(labelAngle=0)),
            y=alt.Y(
                f"{value_column}:Q",
                title=None,
                scale=alt.Scale(domain=[y_min - padding, y_max + padding]),
            ),
            color=alt.Color(
                "spiller:N",
                scale=alt.Scale(domain=player_order),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=["spiller", "runde", value_column],
        )

        latest_points_df = (
            chart_df.sort_values(["spiller", "runde"]).groupby("spiller", as_index=False).tail(1).copy()
        )
        earliest_points_df = (
            chart_df.sort_values(["spiller", "runde"]).groupby("spiller", as_index=False).head(1).copy()
        )

        line_chart = base_chart.mark_line(point=True)
        highlighted_player_chart = (
            base_chart.transform_filter(alt.datum.is_current_player)
            .mark_line(point=alt.OverlayMarkDef(size=95), strokeWidth=4)
        )
        player_labels = (
            alt.Chart(latest_points_df)
            .transform_filter("!datum.is_current_player")
            .mark_text(align="right", baseline="middle", dx=-6, fontSize=10, fontWeight="normal")
            .encode(
                x=alt.X("runde:O", sort="ascending"),
                y=alt.Y(f"{value_column}:Q"),
                color=alt.Color("spiller:N", scale=alt.Scale(domain=player_order), legend=None),
                text=alt.Text("spiller:N"),
            )
        )
        current_player_label = (
            alt.Chart(latest_points_df)
            .transform_filter(alt.datum.is_current_player)
            .mark_text(align="right", baseline="middle", dx=-6, fontSize=10, fontWeight="bold")
            .encode(
                x=alt.X("runde:O", sort="ascending"),
                y=alt.Y(f"{value_column}:Q"),
                color=alt.Color("spiller:N", scale=alt.Scale(domain=player_order), legend=None),
                text=alt.Text("spiller:N"),
            )
        )
        st.altair_chart(
            (line_chart + highlighted_player_chart + player_labels + current_player_label).interactive(),
            width="stretch",
        )

        course_chart_df = my_dfs.resultat_bane_stacked(tournament_id, valgt_verdi)
        if not course_chart_df.empty:
            course_chart_df, bane_order, player_order, chart_title = prepare_course_chart_df(course_chart_df, valgt_verdi)
            total_chart_df = course_chart_df[["spiller", "total"]].drop_duplicates().copy()
            total_chart_df["is_current_player"] = total_chart_df["spiller"].astype(str).eq(current_player)
            total_chart_df["total_label"] = total_chart_df["total"].map(format_numeric_value)

            bars = (
                alt.Chart(course_chart_df)
                .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X(
                        "spiller:N",
                        title=None,
                        sort=player_order,
                        axis=alt.Axis(labelAngle=0, labels=False, ticks=False, domain=False),
                    ),
                    y=alt.Y("value:Q", title=None, stack="zero", axis=None),
                    color=alt.Color(
                        "bane:N",
                        title="Bane",
                        sort=bane_order,
                        legend=alt.Legend(orient="bottom", direction="horizontal"),
                    ),
                    order=alt.Order("bane_order:Q", sort="ascending"),
                    tooltip=[
                        alt.Tooltip("spiller:N", title="Spiller"),
                        alt.Tooltip("bane:N", title="Bane"),
                        alt.Tooltip("value:Q", title=chart_title, format=".12~g"),
                        alt.Tooltip("total:Q", title="Total", format=".12~g"),
                    ],
                )
            )

            total_labels = (
                alt.Chart(total_chart_df)
                .mark_text(dy=-8, fontSize=12, fontWeight="bold", color="#183c34", baseline="bottom")
                .encode(
                    x=alt.X("spiller:N", sort=player_order),
                    y=alt.Y("total:Q"),
                    text=alt.Text("total_label:N"),
                )
            )

            value_labels = (
                alt.Chart(course_chart_df)
                .mark_text(fontSize=12, fontWeight="bold", color="white", baseline="middle")
                .encode(
                    x=alt.X("spiller:N", sort=player_order),
                    y=alt.Y("label_y:Q"),
                    detail="bane:N",
                    text=alt.Text("value:Q", format=".12~g"),
                    order=alt.Order("bane_order:Q", sort="ascending"),
                )
                .properties()
            )

            value_labels = value_labels.encode(tooltip=alt.value(None))

            player_name_labels = (
                alt.Chart(total_chart_df)
                .transform_filter("!datum.is_current_player")
                .mark_text(align="center", baseline="middle", fontSize=12, color="#cbd5e1")
                .encode(
                    x=alt.X("spiller:N", sort=player_order, title=None, axis=None),
                    y=alt.value(16),
                    text=alt.Text("spiller:N"),
                )
            )

            current_player_name_label = (
                alt.Chart(total_chart_df)
                .transform_filter(alt.datum.is_current_player)
                .mark_text(align="center", baseline="middle", fontSize=15, fontWeight="bold", color=CHART_COLORS[0])
                .encode(
                    x=alt.X("spiller:N", sort=player_order, title=None, axis=None),
                    y=alt.value(16),
                    text=alt.Text("spiller:N"),
                )
            )

            labels_chart = (player_name_labels + current_player_name_label).properties(height=32)
            main_course_chart = (bars + value_labels + total_labels).properties(height=420)

            st.altair_chart(
                alt.vconcat(main_course_chart, labels_chart, spacing=0).resolve_scale(x="shared"),
                width="stretch",
            )

        round_option_values, round_option_labels, round_label_to_value = build_round_selector_options(
            tournament_round_info_df,
            round_label_map,
        )
        valgt_runde = st.selectbox(
            "Velg runde:",
            options=round_option_labels,
            index=len(round_option_labels) - 1,
        )
        selected_runde = round_info_df.loc[
            (round_info_df["turneringsid"].astype(str) == str(tournament_id))
            & pd.to_numeric(round_info_df["runde"], errors="coerce").eq(round_label_to_value[valgt_runde])
        ]
        if not selected_runde.empty:
            _render_round_badges(
                my_dfs.get_spillermerker_df(),
                current_player,
                str(selected_runde.iloc[0]["rundeid"]),
            )
        st.dataframe(my_dfs.resultat_pr_hull(tournament_id, round_label_to_value[valgt_runde], valgt_verdi), height=540, width="stretch")
        st.divider()
        st.subheader(f"Birdie og sånn, runde {valgt_runde}")
        st.dataframe(
            format_numeric_df(my_dfs.resultat_annet_goy_eagle_osv(tournament_id, round_label_to_value[valgt_runde])),
            width="stretch",
            hide_index=True,
        )

    with tab_annet:
        valgt_visning = st.segmented_control(
            "Velg visning",
            options=FUN_OPTIONS,
            selection_mode="single",
            default=FUN_OPTIONS[0],
            label_visibility="collapsed",
        ) or FUN_OPTIONS[0]

        if valgt_visning == "Birdie og sånn":
            df = my_dfs.resultat_annet_goy_eagle_osv(tournament_id)
            st.dataframe(format_numeric_df(df), width="stretch", hide_index=True)

        if valgt_visning == "Gruppen pr runde":
            st.dataframe(format_numeric_df(my_dfs.resultat_goy_gruppen_runde(tournament_id)), width="stretch", hide_index=True)

        if valgt_visning == "Pall-plasser":
            df = my_dfs.resultat_goy_pall(tournament_id)
            st.dataframe(format_numeric_df(df), width="stretch", hide_index=True)