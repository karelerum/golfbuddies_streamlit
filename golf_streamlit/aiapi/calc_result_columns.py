"""
Compute scoring columns for a specific round (or all rounds)
Called from: auto-detect, admin panel, etc.

⚠️ IMPORTANT: After making changes to this file, ALWAYS run:
   python test_scoring.py -v
   
Tests cover:
  - P6 tie-sharing (2+ players tied should share points equally)
  - P6 penalty rule (slag > par+5 gets 0 points)
  - P1 tie-sharing for winners
  - P1 penalty rule
  - Max slag validation (no one exceeds par+6)
  - Data integrity checks
"""
import sqlite3
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def recalculate_placement(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append or recalculate the 'plass' column in the DataFrame based on the current slag and tie rules.
    If tie the next position(s) should be skipped. For example, if 2 players tie for 1st place, they both get plass=1 and the next player gets plass=3 (not 2).

    Args:
        df: DataFrame with columns slag, rundeid, hull + rest       
    Returns:
        DataFrame with updated 'plass' column
    """
    df["plass"] = (
        df.groupby(["rundeid", "hull"])["slag"]
        .rank(method="min")
        .astype(int)
    )
    return df

def recalculate_6points(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append or recalculate the p6 column in the DataFrame based on the current slag, plass, and tie rules.
    
    Args:
        df: DataFrame with columns slag, plass, par, rundeid, hull + rest
        plass is expected to be already calculated and should reflect ties (i.e., multiple players can have plass=1 if they tie for first)
        hvis slag > par + 5, p6 = 0
    Returns:
        DataFrame with updated p6 column
    """
    base_points = {1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}
    # points beyond plass 6 are always 0, so the running total caps out there
    prefix_sums = np.concatenate(([0], np.cumsum([base_points.get(pos, 0) for pos in range(1, 7)])))

    def _prefix(positions: pd.Series) -> np.ndarray:
        return prefix_sums[positions.clip(lower=0, upper=6).astype(int).to_numpy()]

    plass = df["plass"]
    ties_at_plass = df.groupby(["rundeid", "hull", "plass"])["plass"].transform("count")

    total_points = _prefix(plass + ties_at_plass - 1) - _prefix(plass - 1)
    avg_points = np.divide(total_points, ties_at_plass, out=np.zeros(len(df), dtype=float), where=ties_at_plass.to_numpy() > 0)

    penalty_mask = (df["slag"] > df["par"] + 5).to_numpy()
    df["p6"] = np.where(penalty_mask, 0, avg_points)
    return df


def recalculate_slag_round_points(df: pd.DataFrame) -> pd.DataFrame:
    """Set p6 from total round strokes: 18, 15, 12, 9, 6, 3, then 0."""
    points_by_place = {1: 18, 2: 15, 3: 12, 4: 9, 5: 6, 6: 3}
    total_rank_df = df.groupby(["rundeid", "spiller"], as_index=False)["slag"].sum()
    total_rank_df = total_rank_df.rename(columns={"slag": "total_slag"})
    total_rank_df["total_plass"] = total_rank_df.groupby("rundeid")["total_slag"].rank(method="min", ascending=True)
    df = df.drop(columns=["p6"], errors="ignore").merge(
        total_rank_df[["rundeid", "spiller", "total_plass"]],
        on=["rundeid", "spiller"],
        how="left",
        sort=False,
    )
    df["p6"] = df["total_plass"].map(lambda place: points_by_place.get(int(place), 0))
    df = df.drop(columns=["total_plass"])
    return df

def recalculate_p1(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append or recalculate the p1 column in the DataFrame based on the current slag, plass, and tie rules.
    For p1, only players with plass=1 get points, and if multiple players tie for first, they share the point equally.

    Args:
        df: DataFrame with columns slag, plass, par, rundeid, hull + rest
        plass is expected to be already calculated and should reflect ties (i.e., multiple players can have plass=1 if they tie for first)
    Returns:
        DataFrame with updated p1 column
    """
    df["p1"] = (
        (df["plass"] == 1).astype(float) / 
        df.groupby(["rundeid", "hull"])["plass"].transform(lambda x: (x == 1).sum())
    ).round(2)
    return df

def recalculate_spiller_par(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append or recalculate the spiller_par column in the DataFrame based on the current slag and par values.
    
    Args:
        df: DataFrame with columns slag, par, rundeid, hull + rest
    Returns:
        DataFrame with updated spiller_par column
    """
    df["spiller_par"] = df["slag"] - df["par"]
    return df

def recalculate_par_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append or recalculate hole result type columns (hole_in_one, eagle, birdie, par_ind, bogey, double_bogey, triple_bogey, other_ind) based on spiller_par.
    
    Args:
        df: DataFrame with columns spiller_par, rundeid, hull + rest
    Returns:
        DataFrame with updated hole result type columns
    """
    df["hole_in_one"] = (df["slag"] == 1).astype(int)
    df["eagle"] = ((df["spiller_par"] == -2) & (df["slag"] != 1)).astype(int)
    df["birdie"] = (df["spiller_par"] == -1).astype(int)
    df["par_ind"] = (df["spiller_par"] == 0).astype(int)
    df["bogey"] = (df["spiller_par"] == 1).astype(int)
    df["double_bogey"] = (df["spiller_par"] == 2).astype(int)
    df["triple_bogey"] = (df["spiller_par"] == 3).astype(int)
    df["other_ind"] = (df["spiller_par"] > 3).astype(int)
    return df

def recalculate_all(df: pd.DataFrame, slag_runde: bool = False) -> pd.DataFrame:
    """
    Append or recalculate all scoring columns in the DataFrame based on the current slag, par, and tie rules.
    
    Args:
        df: DataFrame with columns slag, par, rundeid, hull + rest
    Returns:
        DataFrame with all updated scoring columns
    """ 
    
    df = recalculate_placement(df)
    if slag_runde:
        df = recalculate_slag_round_points(df)
    else:
        df = recalculate_6points(df)
    df = recalculate_p1(df)
    df = recalculate_spiller_par(df)
    df = recalculate_par_types(df)
    return df