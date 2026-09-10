from dataclasses import dataclass

import pandas as pd

from aiapi.back_df_round import _merge_edited_round_df, _prepare_round_df, _update_round_completion_status
from aiapi.df_general_cached import set_cached_df
from aiapi.gsheet_sync import SyncReport, sync_df_to_gsheet
from aiapi.round_result import add_or_update_round_to_result
from src import badge_calc
from src import my_dfs


class RoundSaveError(RuntimeError):
    """Raised when saving a round fails and the UI needs a clear message."""


@dataclass
class RoundSaveResult:
    round_df: pd.DataFrame
    round_info_df: pd.DataFrame
    result_df: pd.DataFrame
    spillermerker_df: pd.DataFrame
    sync_report: SyncReport


def save_round_and_sync(
    rundeid,
    prepared_round_df: pd.DataFrame,
    edited_round_df: pd.DataFrame,
    is_round_completed: bool,
) -> RoundSaveResult:
    try:
        validated_edited_df = _prepare_round_df(edited_round_df)
        round_to_save = _merge_edited_round_df(prepared_round_df, validated_edited_df)
        round_info_to_save = _update_round_completion_status(
            my_dfs.get_round_info_df(),
            rundeid,
            is_round_completed,
        )
    except Exception as exc:
        raise RoundSaveError(f"Klarte ikke å klargjore runde {rundeid} for lagring: {exc}") from exc

    try:
        saved = my_dfs.save_round_df(rundeid, round_to_save)
        if not saved:
            raise RoundSaveError(f"Klarte ikke å lagre runde {rundeid}.")

        round_info_saved = my_dfs.save_round_info_df(round_info_to_save)
        if not round_info_saved:
            raise RoundSaveError(f"Klarte ikke å lagre status for runde {rundeid}.")
    except RoundSaveError:
        raise
    except Exception as exc:
        raise RoundSaveError(f"Klarte ikke å lagre runde {rundeid}: {exc}") from exc

    try:
        result_df = add_or_update_round_to_result(rundeid)
    except Exception as exc:
        raise RoundSaveError(f"Runde {rundeid} ble lagret, men resultat kunne ikke oppdateres: {exc}") from exc

    try:
        spillermerker_df = badge_calc.calculate_achievements(df_resultater=result_df)
        spillermerker_saved = my_dfs.save_table_df("spillermerker", spillermerker_df)
        if not spillermerker_saved:
            raise RoundSaveError("Resultat ble oppdatert, men klarte ikke lagre spillermerker.")
        try:
            set_cached_df("spillermerker", spillermerker_df)
        except Exception:
            # Cache er best-effort; SQLite er sannhetskilden.
            pass
    except RoundSaveError:
        raise
    except Exception as exc:
        raise RoundSaveError(f"Resultat ble oppdatert, men beregning/lagring av spillermerker feilet: {exc}") from exc

    sync_report = SyncReport()
    sync_report.extend(sync_df_to_gsheet(round_to_save, "rounds", str(rundeid)))
    sync_report.extend(sync_df_to_gsheet(round_info_to_save, "master", "rundeinfo"))
    sync_report.extend(sync_df_to_gsheet(result_df, "master", "resultat"))
    sync_report.extend(sync_df_to_gsheet(spillermerker_df, "master", "spillermerker"))

    return RoundSaveResult(
        round_df=round_to_save,
        round_info_df=round_info_to_save,
        result_df=result_df,
        spillermerker_df=spillermerker_df,
        sync_report=sync_report,
    )