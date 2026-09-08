import pandas as pd
import streamlit as st

from aiapi.back_df_round import (
	_get_default_round_id,
	_get_round_options,
	_get_round_summary,
	_get_score_validation_messages,
	_get_visible_player_columns,
	_calculate_round_totals,
	_is_admin_player,
	_prepare_round_df,
)
from aiapi.round_save import RoundSaveError, save_round_and_sync
from src import my_dfs


def page():
	st.title("Registrer slag")
	success_message = st.session_state.pop("registrer_slag_success_message", None)
	if success_message:
		st.success(success_message)

	round_options = _get_round_options()
	default_round_id = _get_default_round_id(round_options)
	default_index = round_options.index(default_round_id) if default_round_id in round_options else 0
	selected_round = st.selectbox("Velg runde", options=round_options, index=default_index)
	round_summary = _get_round_summary(selected_round)
	current_player = st.session_state.get("innlogget_spiller")

	st.subheader(f"{round_summary['turneringsnavn']} - Runde {round_summary['runde']}")
	meta_col1, meta_col2, meta_col3 = st.columns(3)
	with meta_col1:
		st.caption("Bane")
		st.text(round_summary["bane"])
	with meta_col2:
		st.caption("Status")
		if _is_admin_player(current_player):
			is_round_completed = st.toggle(
				"Fullført",
				value=bool(round_summary["ferdig_ind"]),
				key=f"round_completed_toggle_{selected_round}",
			)
		else:
			st.text(round_summary["status"])
	with meta_col3:
		st.caption("Turnering")
		st.text(round_summary["turneringsnavn"])

	if not _is_admin_player(current_player):
		is_round_completed = bool(round_summary["ferdig_ind"])

	round_df = my_dfs.get_round_df(selected_round)
	prepared_df = _prepare_round_df(round_df)
	show_all_players = False
	if _is_admin_player(current_player):
		show_all_players = st.toggle("Vis alle spillere", value=False)

	visible_player_columns = _get_visible_player_columns(prepared_df, current_player, show_all_players)
	display_df = prepared_df[["hull"] + visible_player_columns].copy()
	editor_height = max(500, 45 + max(len(prepared_df), 18) * 35)

	edited_df = st.data_editor(
		display_df,
		height=editor_height,
		hide_index=True,
		width="stretch",
		disabled=["hull"],
		column_config={
			"hull": st.column_config.NumberColumn("Hull", format="%d"),
			**{
				column: st.column_config.NumberColumn(
					column,
					min_value=1,
					step=1,
					format="%d",
				)
				for column in visible_player_columns
			},
		},
		key=f"round_editor_{selected_round}",
	)

	warning_messages = _get_score_validation_messages(edited_df, selected_round, visible_player_columns)
	if warning_messages:
		st.warning(f"{len(warning_messages)} registreringer er over par + 6.")
		with st.expander("Vis valideringsdetaljer"):
			for message in warning_messages:
				st.write(f"- {message}")

	st.divider()
	round_totals = _calculate_round_totals(edited_df, visible_player_columns)
	total_columns = st.columns(len(visible_player_columns))
	for index, player_column in enumerate(visible_player_columns):
		with total_columns[index]:
			st.metric(player_column, str(round_totals[player_column]))

	can_save_round = _is_admin_player(current_player) or round_summary["status"] != "Fullført"
	if not can_save_round:
		return

	save_button_placeholder = st.empty()
	if save_button_placeholder.button("Lagre", type="primary", width="stretch"):
		save_button_placeholder.empty()
		with st.spinner("Lagrer og synkroniserer..."):
			try:
				save_result = save_round_and_sync(
					selected_round,
					prepared_df,
					edited_df,
					is_round_completed,
				)
			except RoundSaveError as exc:
				st.error(str(exc))
				return

			sync_report = save_result.sync_report
			if not sync_report.ok:
				st.warning(sync_report.status_message())
				with st.expander("Vis sync-detaljer"):
					for issue in sync_report.issues:
						st.write(f"- {issue.to_display_text()}")
				return

		st.session_state["registrer_slag_success_message"] = "Lagret OK"
		st.rerun()
