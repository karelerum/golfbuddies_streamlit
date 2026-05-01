from dataclasses import dataclass


@dataclass
class ScoreEntry:
    round_id: str
    player: str
    hole_number: int
    strokes: int
