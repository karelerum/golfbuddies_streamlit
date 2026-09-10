import pandas as pd


def get_completed_tournament_results(
    result_df: pd.DataFrame | None,
    round_info_df: pd.DataFrame | None,
    turneringsid,
    extra_round_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Merge result rows with round metadata and keep completed rounds for one tournament."""
    if result_df is None or result_df.empty:
        return pd.DataFrame()

    if round_info_df is None or round_info_df.empty:
        raise ValueError("Fant ingen rundeinfo for resultatvisning.")

    requested_extra_columns = extra_round_columns or []
    required_round_columns = {"rundeid", "turneringsid", "runde", "ferdig_ind", *requested_extra_columns}
    missing_columns = required_round_columns.difference(round_info_df.columns)
    if missing_columns:
        missing_display = ", ".join(sorted(missing_columns))
        raise ValueError(f"rundeinfo mangler kolonner for resultatvisning: {missing_display}")

    normalized_result_df = result_df.copy()
    normalized_result_df["rundeid"] = normalized_result_df["rundeid"].astype(str)

    selected_columns = ["rundeid", "turneringsid", "runde", "ferdig_ind", *requested_extra_columns]
    normalized_round_info_df = round_info_df[selected_columns].copy()
    normalized_round_info_df["rundeid"] = normalized_round_info_df["rundeid"].astype(str)
    normalized_round_info_df["turneringsid"] = normalized_round_info_df["turneringsid"].astype(str)
    normalized_round_info_df["runde"] = pd.to_numeric(normalized_round_info_df["runde"], errors="coerce").astype("Int64")
    normalized_round_info_df["ferdig_ind"] = (
        pd.to_numeric(normalized_round_info_df["ferdig_ind"], errors="coerce").fillna(0).astype(int)
    )

    merged_df = normalized_result_df.merge(normalized_round_info_df, on="rundeid", how="left")
    tournament_mask = merged_df["turneringsid"].astype(str) == str(turneringsid)
    completed_mask = merged_df["ferdig_ind"] == 1
    return merged_df.loc[tournament_mask & completed_mask].copy()