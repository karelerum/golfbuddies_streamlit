import altair as alt
import streamlit as st

from aiapi.auth import logout
from aiapi.player_views import (
	PLAYER_TOURNAMENT_FILTERS,
	PLAYER_VALUE_COLUMNS,
	build_player_round_history,
	filter_player_round_history,
	format_player_value_label,
)
from src import my_dfs
from config.design_tokens import SEASON_COLORS


def page():
	current_player = st.session_state.get("innlogget_spiller")

	if not current_player:
		st.warning("Du må være logget inn for å se spiller-siden.")
		return

	st.subheader("Runder")

	valgt_verdi = st.segmented_control(
		"Velg verdi",
		options=list(PLAYER_VALUE_COLUMNS.keys()),
		selection_mode="single",
		default="P6",
		label_visibility="collapsed",
		key="player_value_selection",
	) or "P6"

	valgt_turnering_filter = st.segmented_control(
		"Velg turneringstype",
		options=list(PLAYER_TOURNAMENT_FILTERS.keys()),
		selection_mode="single",
		default="Begge",
		label_visibility="collapsed",
		key="player_tournament_filter",
	) or "Begge"

	round_history_df = build_player_round_history(
		my_dfs.get_result_df(),
		my_dfs.get_round_info_df(),
		my_dfs.get_tournament_info_df(),
		current_player,
	)
	filtered_round_history_df = filter_player_round_history(round_history_df, valgt_turnering_filter)

	if filtered_round_history_df.empty:
		st.info("Fant ingen fullførte runder for valgt filter.")
	else:
		value_column = PLAYER_VALUE_COLUMNS[valgt_verdi]
		filtered_round_history_df = filtered_round_history_df.copy()
		filtered_round_history_df["value_label"] = filtered_round_history_df[value_column].apply(
			lambda value: format_player_value_label(valgt_verdi, value)
		)
		bar_color = alt.Color(
			"type:N",
			title=None,
			scale=alt.Scale(domain=["Sommer", "Vinter"], range=[SEASON_COLORS["Sommer"], SEASON_COLORS["Vinter"]]),
			legend=alt.Legend(orient="top"),
		)

		bars = (
			alt.Chart(filtered_round_history_df)
			.mark_bar(cornerRadiusEnd=6)
			.encode(
				y=alt.Y(
					"round_label:N",
					title=None,
					sort=filtered_round_history_df["round_label"].tolist(),
					axis=alt.Axis(ticks=False, domain=False, title=None, labelLimit=280),
				),
				x=alt.X(
					f"{value_column}:Q",
					title=None,
					axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None),
				),
				color=bar_color,
				tooltip=[
					alt.Tooltip("rundeid:N", title="RundeId"),
					alt.Tooltip("turneringsnavn:N", title="Turnering"),
					alt.Tooltip("type:N", title="Type"),
					alt.Tooltip("bane:N", title="Bane"),
					alt.Tooltip("p6:Q", title="P6", format=".12~g"),
					alt.Tooltip("slag:Q", title="Slag", format=".12~g"),
					alt.Tooltip("plass:Q", title="Plass", format=".12~g"),
					alt.Tooltip("mitt_par:Q", title="Mitt par", format=".12~g"),
				],
			)
		)

		labels = (
			alt.Chart(filtered_round_history_df)
			.mark_text(align="right", baseline="middle", dx=-8, fontSize=12, fontWeight="bold", color="white")
			.encode(
				y=alt.Y("round_label:N", sort=filtered_round_history_df["round_label"].tolist()),
				x=alt.X(f"{value_column}:Q"),
				text=alt.Text("value_label:N"),
			)
		)

		chart_height = max(240, len(filtered_round_history_df) * 44)
		st.altair_chart((bars + labels).properties(height=chart_height), width="stretch")

	if st.button("Logg ut", type="secondary"):
		logout()
		st.rerun()
