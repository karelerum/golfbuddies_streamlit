import streamlit as st

from aiapi.admin_tasks import AdminTaskError, run_full_sync_task, run_single_table_sync_task
from src.my_dfs import get_table_list

def page():
    """Hovedfunksjon for admin sync-side."""
    st.title("Sjekk Sync")

    table_list = get_table_list()
    table_options = []
    if table_list is not None and not table_list.empty and {"source", "worksheet"}.issubset(table_list.columns):
        unique_rows = table_list[["source", "worksheet"]].dropna().drop_duplicates()
        table_options = [
            (str(row.source), str(row.worksheet))
            for row in unique_rows.itertuples(index=False)
        ]

    st.subheader("Hent enkelt-tabell fra Google Sheets")
    if table_options:
        selected_source, selected_worksheet = st.selectbox(
            "Velg tabell",
            options=table_options,
            format_func=lambda item: f"{item[0]} / {item[1]}",
        )

        if st.button("Hent tabell"):
            try:
                task_result = run_single_table_sync_task(selected_source, selected_worksheet)
            except AdminTaskError as exc:
                st.error(str(exc))
            else:
                elapsed_text = f" ({task_result.elapsed_seconds:.1f} sek)" if task_result.elapsed_seconds is not None else ""
                if task_result.ok:
                    row_text = f" ({task_result.row_count} rader)" if task_result.row_count is not None else ""
                    st.success(f"{task_result.message}{row_text}{elapsed_text}")
                else:
                    st.warning(f"{task_result.message}{elapsed_text}")
                if task_result.sync_report.issues:
                    with st.expander("Vis detaljer"):
                        for issue in task_result.sync_report.issues:
                            st.write(f"- {issue.to_display_text()}")
    else:
        st.info("Fant ingen tabeller i worksheet_list. Kjør full sync først.")

    st.divider()
    
    if st.button("Hent alt fra google sheet"):
        try:
            task_result = run_full_sync_task()
        except AdminTaskError as exc:
            st.error(str(exc))
        else:
            elapsed_text = f" ({task_result.elapsed_seconds:.1f} sek)" if task_result.elapsed_seconds is not None else ""
            if task_result.ok:
                st.success(f"{task_result.message}{elapsed_text}")
            else:
                st.warning(f"{task_result.message}{elapsed_text}")
            if task_result.sync_report.issues:
                with st.expander("Vis detaljer"):
                    for issue in task_result.sync_report.issues:
                        st.write(f"- {issue.to_display_text()}")
    
    # Tabell over alle tilgjengelige worksheets
    st.subheader("Tilgjengelige worksheets")
    
    if table_list is not None:
        st.table(table_list)
    else:
        st.write("Ingen worksheets tilgjengelig.")


