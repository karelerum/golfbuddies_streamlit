"""Convert completed live scorecards into one stable ordinary-round scorecard."""

from fractions import Fraction
import math

import pandas as pd


def _as_fraction(value) -> Fraction:
    return Fraction(str(value))


def _round_half_up(value: Fraction) -> int:
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def _build_player_average_data(
    score_dfs: list[pd.DataFrame],
    player_name: str,
    holes: list[int],
) -> tuple[dict[int, Fraction], dict[int, int], dict[int, Fraction]]:
    averages: dict[int, Fraction] = {}
    floors: dict[int, int] = {}
    fractions: dict[int, Fraction] = {}

    for hole in holes:
        values = []
        for score_df in score_dfs:
            if player_name not in score_df.columns:
                continue
            hole_values = score_df.loc[
                pd.to_numeric(score_df["hull"], errors="coerce").eq(hole), player_name
            ]
            values.extend(pd.to_numeric(hole_values, errors="coerce").dropna().tolist())
        if not values:
            continue
        average = sum((_as_fraction(value) for value in values), Fraction(0)) / len(values)
        floor_value = math.floor(average)
        averages[hole] = average
        floors[hole] = floor_value
        fractions[hole] = average - floor_value

    return averages, floors, fractions


def _allocate_player_scores(
    floors: dict[int, int],
    fractions: dict[int, Fraction],
    target_total: int,
) -> dict[int, int]:
    allocated = floors.copy()
    strokes_to_add = target_total - sum(floors.values())
    ranked_holes = sorted(fractions, key=lambda hole: (-fractions[hole], hole))
    for hole in ranked_holes[:max(0, strokes_to_add)]:
        allocated[hole] += 1
    return allocated


def _remove_strokes(
    scores: dict[int, int],
    floors: dict[int, int],
    fractions: dict[int, Fraction],
    strokes: int,
) -> None:
    """Remove the least faithful added strokes first, never going below one."""
    candidates = sorted(
        scores,
        key=lambda hole: (
            0 if scores[hole] > floors[hole] else 1,
            fractions[hole],
            hole,
        ),
    )
    for hole in candidates:
        while strokes and scores[hole] > 1:
            scores[hole] -= 1
            strokes -= 1
        if not strokes:
            return


def _preserve_ranking(
    scores_by_player: dict[str, dict[int, int]],
    exact_totals: dict[str, Fraction],
    floor_data: dict[str, tuple[dict[int, int], dict[int, Fraction]]],
) -> None:
    """Keep lower exact totals at least as good as higher exact totals."""
    player_order = sorted(exact_totals, key=lambda player: (exact_totals[player], player))
    for better_player, worse_player in zip(player_order, player_order[1:]):
        better_total = sum(scores_by_player[better_player].values())
        worse_total = sum(scores_by_player[worse_player].values())
        if better_total > worse_total:
            floors, fractions = floor_data[better_player]
            _remove_strokes(
                scores_by_player[better_player],
                floors,
                fractions,
                better_total - worse_total,
            )


def calculate_live_round_df(
    source_round_df: pd.DataFrame,
    score_dfs: list[pd.DataFrame],
    player_names: list[str],
) -> pd.DataFrame:
    """Build integer scores from live-round averages without changing ranking order."""
    if source_round_df is None or source_round_df.empty or "hull" not in source_round_df.columns:
        raise ValueError("Krever et scorekort med hull-kolonne.")
    if not score_dfs:
        raise ValueError("Krever minst ett live-scorekort.")

    result_df = source_round_df[["hull"]].copy()
    result_df["hull"] = pd.to_numeric(result_df["hull"], errors="coerce").astype("Int64")
    result_df = result_df.dropna(subset=["hull"]).reset_index(drop=True)
    holes = result_df["hull"].astype(int).tolist()

    scores_by_player: dict[str, dict[int, int]] = {}
    exact_totals: dict[str, Fraction] = {}
    floor_data: dict[str, tuple[dict[int, int], dict[int, Fraction]]] = {}
    output_values: dict[str, list[int | pd._libs.missing.NAType]] = {}

    for player_name in player_names:
        averages, floors, fractions = _build_player_average_data(score_dfs, player_name, holes)
        if not averages:
            output_values[player_name] = [pd.NA] * len(holes)
            continue
        exact_totals[player_name] = sum(averages.values(), Fraction(0))
        target_total = _round_half_up(exact_totals[player_name])
        scores = _allocate_player_scores(floors, fractions, target_total)
        scores_by_player[player_name] = scores
        floor_data[player_name] = (floors, fractions)

    _preserve_ranking(scores_by_player, exact_totals, floor_data)

    for player_name in player_names:
        scores = scores_by_player.get(player_name, {})
        output_values[player_name] = [scores.get(hole, pd.NA) for hole in holes]
        result_df[player_name] = pd.array(output_values[player_name], dtype="Int64")

    return result_df
