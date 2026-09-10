from datetime import datetime

import streamlit as st

from aiapi.admin_tasks import AdminTaskError, rebuild_result_task
from aiapi.sqlite import get_countdown_timer_deadline, set_countdown_timer_deadline
from config.constants import DEFAULT_COUNTDOWN_TIMER_DEADLINE


def page():
	st.title("Diverse admin")

	if st.button("Rekalkuler hele resultat og synk til Google Sheets"):
		try:
			task_result = rebuild_result_task()
		except AdminTaskError as exc:
			st.error(str(exc))
		else:
			if task_result.ok:
				st.success(task_result.message)
			else:
				st.warning(task_result.sync_report.status_message())
			if task_result.sync_report.issues:
				with st.expander("Vis detaljer"):
					for issue in task_result.sync_report.issues:
						st.write(f"- {issue.to_display_text()}")

	st.divider()
	st.subheader("Nedtelling")

	current_deadline = get_countdown_timer_deadline() or DEFAULT_COUNTDOWN_TIMER_DEADLINE
	col_date, col_time = st.columns(2)
	new_date = col_date.date_input("Sluttdato", value=current_deadline.date())
	new_time = col_time.time_input("Slutt-klokkeslett", value=current_deadline.time())

	if st.button("Lagre nedtelling"):
		if set_countdown_timer_deadline(datetime.combine(new_date, new_time)):
			st.success("Nedtelling oppdatert.")
		else:
			st.error("Klarte ikke å lagre nedtelling.")
