"""Badge PNGs as base64 data URIs, embedded into the register_btns frontend component."""

import base64
from functools import lru_cache
from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets" / "badges"

_BADGE_FILES = {
    "hole_in_one": "hole_in_one.png",
    "eagle": "eagle.png",
    "birdie": "1_birdie.png",
}


@lru_cache(maxsize=None)
def get_badge_data_uris() -> dict[str, str]:
    """Read each badge PNG once and return {score_type: data-uri} for use as a component arg."""
    uris = {}
    for score_type, filename in _BADGE_FILES.items():
        encoded = base64.b64encode((_ASSETS_DIR / filename).read_bytes()).decode("ascii")
        uris[score_type] = f"data:image/png;base64,{encoded}"
    return uris
