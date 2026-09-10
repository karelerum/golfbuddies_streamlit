import pandas as pd

from aiapi.calc_result_columns import recalculate_all
from aiapi.back_df_round import format_round_to_simple_result
from aiapi.gsheet_sync import SyncReport, sync_df_to_gsheet
from aiapi.sqlite import table_exists
from src.my_dfs import get_hole_info_df, get_result_df, get_round_df, get_round_info_df, save_result_df


def _drop_artifact_columns(df: pd.DataFrame) -> pd.DataFrame:
    artifact_columns = [column for column in ["index", "level_0"] if column in df.columns]
    if not artifact_columns:
        return df
    return df.drop(columns=artifact_columns)


def _add_par_to_result_df(result_df: pd.DataFrame, rundeid) -> pd.DataFrame:
    round_info_df = get_round_info_df()
    hole_info_df = get_hole_info_df()

    round_info = round_info_df.loc[round_info_df["rundeid"].astype(str) == str(rundeid)]
    if round_info.empty:
        raise ValueError(f"Fant ikke rundeinfo for rundeid {rundeid}")

    bane = round_info.iloc[0]["bane"]
    par_df = hole_info_df.loc[hole_info_df["bane"] == bane, ["hull", "par"]].copy()
    if par_df.empty:
        raise ValueError(f"Fant ikke hullinfo med par for bane '{bane}'")

    merged_df = result_df.merge(par_df, on="hull", how="left")
    if merged_df["par"].isna().any():
        missing_hulls = sorted(merged_df.loc[merged_df["par"].isna(), "hull"].unique().tolist())
        raise ValueError(f"Fant ikke par for hull {missing_hulls} på bane '{bane}'")

    return merged_df


def _normalize_unique_key_columns(df: pd.DataFrame, unique_columns: list[str]) -> pd.DataFrame:
    normalized_df = df.copy()
    normalized_df["rundeid"] = normalized_df["rundeid"].astype(str)
    normalized_df["hull"] = pd.to_numeric(normalized_df["hull"], errors="raise").astype(int)
    normalized_df["spiller"] = normalized_df["spiller"].astype(str)
    return normalized_df


def _is_enabled_flag(value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "ja", "yes", "y"}


def _calculate_round_result_df(rundeid) -> pd.DataFrame:
    round_df = get_round_df(rundeid)
    simple_result_df = format_round_to_simple_result(round_df, rundeid)
    simple_result_df = _add_par_to_result_df(simple_result_df, rundeid)
    simple_result_df["hull"] = pd.to_numeric(simple_result_df["hull"], errors="raise").astype(int)
    simple_result_df["slag"] = pd.to_numeric(simple_result_df["slag"], errors="raise")
    simple_result_df["par"] = pd.to_numeric(simple_result_df["par"], errors="raise")
    round_info_df = get_round_info_df()
    round_info = round_info_df.loc[round_info_df["rundeid"].astype(str) == str(rundeid)]
    slag_runde = False
    if not round_info.empty and "slag_runde_ind" in round_info.columns:
        flag_value = round_info.iloc[0]["slag_runde_ind"]
        slag_runde = _is_enabled_flag(flag_value)
    recalculated_df = recalculate_all(simple_result_df, slag_runde=slag_runde)
    return _normalize_unique_key_columns(recalculated_df, ["rundeid", "hull", "spiller"])


def add_or_update_round_to_result(rundeid):
    existing_result_df = get_result_df()
    unique_columns = ["rundeid", "hull", "spiller"]
    recalculated_df = _calculate_round_result_df(rundeid)

    if existing_result_df is None or existing_result_df.empty:
        merged_df = recalculated_df.copy()
    else:
        existing_result_df = _drop_artifact_columns(existing_result_df)
        recalculated_df = _drop_artifact_columns(recalculated_df)
        existing_result_df = _normalize_unique_key_columns(existing_result_df, unique_columns)

        for column in existing_result_df.columns:
            if column not in recalculated_df.columns:
                recalculated_df[column] = pd.NA
        for column in recalculated_df.columns:
            if column not in existing_result_df.columns:
                existing_result_df[column] = pd.NA

        recalculated_df = recalculated_df[existing_result_df.columns]

        existing_indexed = existing_result_df.set_index(unique_columns)
        recalculated_indexed = recalculated_df.set_index(unique_columns)
        existing_without_round = existing_indexed.loc[~existing_indexed.index.isin(recalculated_indexed.index)]

        if existing_without_round.empty:
            merged_df = recalculated_indexed.reset_index()
        else:
            merged_columns = existing_result_df.columns.tolist()
            merged_records = (
                existing_without_round.reset_index().to_dict("records")
                + recalculated_indexed.reset_index().to_dict("records")
            )
            merged_df = pd.DataFrame.from_records(merged_records, columns=merged_columns)

    merged_df = merged_df.drop_duplicates(subset=unique_columns, keep="last")
    merged_df = merged_df.sort_values(unique_columns, ascending=False).reset_index(drop=True)
    save_result_df(merged_df)
    return merged_df


def rebuild_result_df(sync_to_gsheet: bool = False) -> tuple[pd.DataFrame, SyncReport]:
    round_info_df = get_round_info_df()
    if round_info_df is None or round_info_df.empty:
        raise ValueError("Fant ingen runder i rundeinfo.")

    round_ids = round_info_df["rundeid"].dropna().astype(str).unique().tolist()
    sync_report = SyncReport()
    recalculated_rounds = []
    for rundeid in round_ids:
        if not table_exists(str(rundeid)):
            continue
        round_df = get_round_df(rundeid)
        if round_df is None or round_df.empty:
            continue
        try:
            recalculated_rounds.append(_calculate_round_result_df(rundeid))
        except Exception as exc:
            sync_report.add_issue("warning", "result/recalculate", str(exc), rundeid)

    if not recalculated_rounds:
        raise ValueError("Fant ingen rundedata å beregne resultat fra.")

    result_df = pd.concat(recalculated_rounds, ignore_index=True, sort=False)
    unique_columns = ["rundeid", "hull", "spiller"]
    result_df = _drop_artifact_columns(result_df)
    result_df = _normalize_unique_key_columns(result_df, unique_columns)
    result_df = result_df.drop_duplicates(subset=unique_columns, keep="last")
    result_df = result_df.sort_values(unique_columns, ascending=False).reset_index(drop=True)
    save_result_df(result_df)

    if sync_to_gsheet:
        sync_report.extend(sync_df_to_gsheet(result_df, "master", "resultat"))

    return result_df, sync_report


def get_tournament_p6_totals(turneringsid: str) -> dict[str, float]:
    """Sum each player's already-earned p6 points across finished rounds in one tournament (used as 6P start values)."""
    result_df = get_result_df()
    if result_df is None or result_df.empty or "p6" not in result_df.columns:
        return {}
    rundeid_prefix = result_df["rundeid"].astype(str).str[: len(str(turneringsid))]
    tournament_df = result_df.loc[rundeid_prefix == str(turneringsid)]
    if tournament_df.empty:
        return {}
    totals = tournament_df.groupby("spiller")["p6"].sum()
    return {str(spiller): float(total) for spiller, total in totals.items()}