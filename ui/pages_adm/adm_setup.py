import streamlit as st

from aiapi.admin_tasks import AdminTaskError, save_master_tables_task
from src import badge_calc, my_dfs


def page():
    st.title("Direkte redigering")

    table_list_df = my_dfs.get_table_list()
    if table_list_df is None or table_list_df.empty:
        st.write("Fant ingen worksheet_list.")
        return

    master_tables = (
        table_list_df.loc[
            (table_list_df["source"].astype(str).str.lower() == "master")
            & (table_list_df["worksheet"].astype(str).str.lower() != "resultat"),
            "worksheet",
        ]
        .astype(str)
        .drop_duplicates()
        .tolist()
    )

    save_requested = st.button("Lagre og Sync alt", type="primary", width="stretch")

    edited_tables = {}
    for table_name in master_tables:
        if table_name.strip().lower() == "spillermerker":
            with st.container(horizontal=True, vertical_alignment="center"):
                st.subheader(table_name)
                if st.button("Rekalkuler", key=f"direct_edit_recalc_{table_name}"):
                    with st.spinner("Rekalkulerer merker..."):
                        try:
                            spillermerker_df = badge_calc.calculate_achievements()
                            my_dfs.save_spillermerker_df(spillermerker_df)
                        except Exception as exc:
                            st.error(f"Klarte ikke å rekalkulere merker: {exc}")
                        else:
                            st.success(f"Merker rekalkulert. Lagret {len(spillermerker_df)} rader i spillermerker.")
                            st.rerun()
        else:
            st.subheader(table_name)
        df = my_dfs.get_table_df(table_name)
        edited_tables[table_name] = st.data_editor(
            df,
            key=f"direct_edit_{table_name}",
            hide_index=True,
            width="stretch",
            num_rows="dynamic",
        )

    if save_requested:
        try:
            task_result = save_master_tables_task(edited_tables)
        except AdminTaskError as exc:
            st.error(str(exc))
        else:
            if task_result.ok:
                st.success(task_result.message)
            else:
                st.warning(task_result.message)
                with st.expander("Vis detaljer"):
                    for issue in task_result.sync_report.issues:
                        st.write(f"- {issue.to_display_text()}")