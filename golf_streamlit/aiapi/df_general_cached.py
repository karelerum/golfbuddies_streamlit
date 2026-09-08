import pandas as pd
import streamlit as st

from .sqlite import get_sqlite_df


def _ensure_cache_store() -> dict[str, pd.DataFrame]:
    if "cached_dfs" not in st.session_state:
        st.session_state.cached_dfs = {}
    return st.session_state.cached_dfs


def _ensure_change_log() -> list[dict]:
    if "df_change_log" not in st.session_state:
        st.session_state.df_change_log = []
    return st.session_state.df_change_log


def set_cached_df(name: str, df: pd.DataFrame) -> None:
    cache_store = _ensure_cache_store()
    cache_store[name] = df
    log_df_change(name)


def get_cached_df(name: str) -> pd.DataFrame | None:
    """Get cached DataFrame, loading it from SQLite on first access."""
    cache_store = _ensure_cache_store()
    if name not in cache_store:
        df = get_sqlite_df(name)
        if df is not None and not df.empty:
            set_cached_df(name, df)
            return df
        return None
    return cache_store.get(name)


def log_df_change(name: str) -> None:
    change_log = _ensure_change_log()
    st.session_state.df_change_log = [log for log in change_log if log["df_name"] != name]
    st.session_state.df_change_log.append(
        {
            "df_name": name,
            "change_time": pd.Timestamp.now(),
        }
    )


def clear_cached_df(name: str) -> None:
    cache_store = _ensure_cache_store()
    cache_store.pop(name, None)
