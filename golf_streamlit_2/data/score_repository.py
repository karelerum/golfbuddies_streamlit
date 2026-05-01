from __future__ import annotations

from typing import Any

from data.google_sheets_client import GoogleSheetsClient
from domain.models import ScoreEntry


class ScoreRepository:
    HOLE_HEADER = "Hull"

    def __init__(self, client: GoogleSheetsClient) -> None:
        self.client = client

    @staticmethod
    def is_round_id(value: str) -> bool:
        text = str(value).strip()
        return len(text) == 8 and text.isdigit()

    def _ensure_base_sheet(self, round_id: str) -> Any:
        ws = self.client.get_or_create_worksheet(round_id, rows=20, cols=16)
        holes = [[self.HOLE_HEADER]] + [[str(i)] for i in range(1, 19)]
        ws.update("A1:A19", holes)
        return ws

    def _ensure_player_columns(self, ws: Any, players: list[str]) -> list[str]:
        headers = ws.row_values(1)
        if not headers or headers[0] != self.HOLE_HEADER:
            ws.update("A1", [[self.HOLE_HEADER]])
            headers = ws.row_values(1)

        for player in players:
            name = str(player).strip()
            if not name:
                continue
            if name not in headers:
                ws.update_cell(1, len(headers) + 1, name)
                headers = ws.row_values(1)
        return headers

    def ensure_round_scorecard(self, round_id: str, players: list[str]) -> None:
        ws = self._ensure_base_sheet(round_id)
        self._ensure_player_columns(ws, players)

    def set_hole_score(self, round_id: str, player: str, hole_number: int, strokes: int) -> None:
        if not self.is_round_id(round_id):
            raise ValueError("round_id må være 8 siffer, f.eks. 20260101")
        if hole_number < 1 or hole_number > 18:
            raise ValueError("hole_number må være mellom 1 og 18")

        ws = self._ensure_base_sheet(round_id)
        headers = self._ensure_player_columns(ws, [player])
        col_idx = headers.index(player) + 1
        row_idx = hole_number + 1
        ws.update_cell(row_idx, col_idx, int(strokes))

    def add_score(self, score: ScoreEntry) -> None:
        self.set_hole_score(
            round_id=score.round_id,
            player=score.player,
            hole_number=score.hole_number,
            strokes=score.strokes,
        )

    def _extract_scores_from_round(self, round_id: str) -> list[dict[str, Any]]:
        ws = self.client.get_or_create_worksheet(round_id)
        values = ws.get_all_values()
        if len(values) < 2:
            return []

        headers = values[0]
        if not headers or headers[0] != self.HOLE_HEADER:
            return []

        out: list[dict[str, Any]] = []
        for row in values[1:19]:
            if not row:
                continue
            hole_raw = row[0] if len(row) > 0 else ""
            if not str(hole_raw).strip().isdigit():
                continue
            hole_number = int(str(hole_raw).strip())

            for idx, player in enumerate(headers[1:], start=1):
                if not str(player).strip():
                    continue
                cell = row[idx] if idx < len(row) else ""
                if not str(cell).strip():
                    continue
                strokes = int(float(cell)) if str(cell).strip().replace(".", "", 1).isdigit() else cell
                out.append(
                    {
                        "round_id": round_id,
                        "player": str(player).strip(),
                        "hole_number": hole_number,
                        "strokes": strokes,
                    }
                )
        return out

    def get_all_scores(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for sheet_name in self.client.get_worksheet_names():
            if not self.is_round_id(sheet_name):
                continue
            rows.extend(self._extract_scores_from_round(sheet_name))
        return rows

    def get_scores_for_player(self, player: str) -> list[dict[str, Any]]:
        rows = self.get_all_scores()
        return [row for row in rows if str(row.get("player", "")).strip() == player]
