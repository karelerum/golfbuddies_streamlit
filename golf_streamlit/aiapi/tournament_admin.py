from dataclasses import dataclass

from aiapi.gsheet_sync import SyncReport
from aiapi.tournament_setup import (
    create_tournament_with_rounds,
    delete_tournament,
    update_tournament_with_rounds,
)


class TournamentAdminError(RuntimeError):
    """Raised when a tournament admin action cannot be completed."""


@dataclass
class TournamentAdminResult:
    message: str
    sync_report: SyncReport

    @property
    def ok(self) -> bool:
        return self.sync_report.ok and self.sync_report.warning_count == 0

    @property
    def notice_level(self) -> str:
        return "success" if self.ok else "warning"


def _validate_tournament_name(turneringsnavn: str) -> str:
    normalized_name = str(turneringsnavn or "").strip()
    if not normalized_name:
        raise TournamentAdminError("Turneringsnavn mangler.")
    return normalized_name


def _validate_players(spillere: list[str]) -> list[str]:
    normalized_players = [str(spiller).strip() for spiller in spillere if str(spiller).strip()]
    if not normalized_players:
        raise TournamentAdminError("Velg minst én spiller.")
    return normalized_players


def _validate_courses(baner: list[str]) -> list[str]:
    normalized_courses = [str(bane).strip() for bane in baner if str(bane).strip()]
    if not normalized_courses:
        raise TournamentAdminError("Velg minst én bane.")
    return normalized_courses


def create_tournament_action(
    turneringsnavn: str,
    turnering_type: str,
    aar: int,
    spillere: list[str],
    baner: list[str],
) -> TournamentAdminResult:
    normalized_name = _validate_tournament_name(turneringsnavn)
    normalized_players = _validate_players(spillere)
    normalized_courses = _validate_courses(baner)

    try:
        turneringsid, sync_report = create_tournament_with_rounds(
            normalized_name,
            str(turnering_type),
            int(aar),
            normalized_players,
            normalized_courses,
        )
    except TournamentAdminError:
        raise
    except Exception as exc:
        raise TournamentAdminError(f"Klarte ikke å opprette turnering: {exc}") from exc

    return TournamentAdminResult(
        message=f"Turnering opprettet: {turneringsid}",
        sync_report=sync_report,
    )


def update_tournament_action(
    turneringsid: str,
    turneringsnavn: str,
    turnering_type: str,
    spillere: list[str],
    round_items: list[dict],
) -> TournamentAdminResult:
    normalized_name = _validate_tournament_name(turneringsnavn)
    normalized_players = _validate_players(spillere)
    normalized_round_items = [item for item in round_items if str(item.get("bane") or "").strip()]
    if not normalized_round_items:
        raise TournamentAdminError("Velg minst én bane.")

    try:
        sync_report = update_tournament_with_rounds(
            str(turneringsid),
            normalized_name,
            str(turnering_type),
            normalized_players,
            normalized_round_items,
        )
    except TournamentAdminError:
        raise
    except Exception as exc:
        raise TournamentAdminError(f"Klarte ikke å oppdatere turnering {turneringsid}: {exc}") from exc

    return TournamentAdminResult(
        message=f"Turnering oppdatert: {turneringsid}",
        sync_report=sync_report,
    )


def delete_tournament_action(turneringsid: str) -> TournamentAdminResult:
    try:
        sync_report = delete_tournament(str(turneringsid))
    except Exception as exc:
        raise TournamentAdminError(f"Klarte ikke å slette turnering {turneringsid}: {exc}") from exc

    return TournamentAdminResult(
        message=f"Turnering slettet: {turneringsid}",
        sync_report=sync_report,
    )