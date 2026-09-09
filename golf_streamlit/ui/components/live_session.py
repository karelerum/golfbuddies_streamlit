"""Validation helpers for browser-session Live Runde restoration."""

from collections.abc import Mapping

LIVE_ROUND_SESSION_VIEWS = frozenset({"slag", "setup"})


def build_live_round_session_payload(session_state: Mapping, current_player: str) -> dict | None:
    """Build the small browser-session payload for an active Live Runde."""
    live_rundeid = session_state.get("live_session_id")
    live_runde_view = session_state.get("live_runde_view")
    if session_state.get("choosen_mainpage") != "Live Runde" or not live_rundeid or live_runde_view not in LIVE_ROUND_SESSION_VIEWS:
        return None

    payload = {
        "player": str(current_player),
        "live_rundeid": str(live_rundeid),
        "live_runde_view": str(live_runde_view),
    }
    active_group = session_state.get("live_active_group")
    if isinstance(active_group, int) and active_group > 0:
        payload["live_active_group"] = active_group
    return payload


def validate_live_round_session_payload(payload: object, current_player: str) -> dict | None:
    """Return a validated payload, or None when browser data must be ignored."""
    if not isinstance(payload, dict):
        return None

    live_rundeid = payload.get("live_rundeid")
    live_runde_view = payload.get("live_runde_view")
    if (
        payload.get("player") != str(current_player)
        or not isinstance(live_rundeid, str)
        or not live_rundeid
        or live_runde_view not in LIVE_ROUND_SESSION_VIEWS
    ):
        return None

    validated_payload = {"live_rundeid": live_rundeid, "live_runde_view": live_runde_view}
    active_group = payload.get("live_active_group")
    if isinstance(active_group, int) and active_group > 0:
        validated_payload["live_active_group"] = active_group
    return validated_payload
