import streamlit as st

from aiapi.admin_tasks import AdminTaskError, rebuild_result_task


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
