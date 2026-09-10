import streamlit as st

from src import badge_calc, my_dfs


def _full_table_height(df):
    # Approx row height in Streamlit dataframe is around 35 px + header.
    return max(140, (len(df) + 1) * 35)


def page():
    st.title("Merker")

    if st.button("Rekalkuler merker", type="primary", width="stretch"):
        with st.spinner("Rekalkulerer merker..."):
            try:
                spillermerker_df = badge_calc.calculate_achievements()
                my_dfs.save_spillermerker_df(spillermerker_df)
            except Exception as exc:
                st.error(f"Klarte ikke a rekalkulere merker: {exc}")
            else:
                st.success(f"Merker rekalkulert. Lagret {len(spillermerker_df)} rader i spillermerker.")

    st.subheader("Spillermerker-tabell")
    spillermerker_df = my_dfs.get_spillermerker_df()
    if spillermerker_df is None or spillermerker_df.empty:
        st.info("Fant ingen data i tabellen 'spillermerker'.")
        return

    merker_df = my_dfs.get_merker_df()
    spillere = []
    if merker_df is not None and not merker_df.empty and "spiller" in merker_df.columns:
        spillere = sorted(
            merker_df["spiller"].dropna().astype(str).str.strip().loc[lambda values: values.ne("")].unique().tolist()
        )

    if not spillere and "spiller" in spillermerker_df.columns:
        spillere = sorted(
            spillermerker_df["spiller"].dropna().astype(str).str.strip().loc[lambda values: values.ne("")].unique().tolist()
        )

    if not spillere:
        st.info("Fant ingen spillere for filtrering.")
        st.dataframe(
            spillermerker_df,
            hide_index=True,
            width="stretch",
            height=_full_table_height(spillermerker_df),
        )
        return

    valgt_spiller = st.selectbox("Velg spiller", options=spillere)
    filtrert_df = spillermerker_df.loc[
        spillermerker_df["spiller"].astype(str).str.strip().eq(str(valgt_spiller).strip())
    ].copy()

    st.caption(f"Viser {len(filtrert_df)} rader for {valgt_spiller}.")
    if filtrert_df.empty:
        st.info("Fant ingen spillermerker for valgt spiller.")
        return

    st.dataframe(
        filtrert_df,
        hide_index=True,
        width="stretch",
        height=_full_table_height(filtrert_df),
    )
