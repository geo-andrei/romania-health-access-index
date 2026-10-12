"""Load settings.yml and resolve paths relative to the repo root."""
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def settings() -> dict:
    with open(ROOT / "config" / "settings.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def path(kind: str, name: str = "") -> Path:
    p = ROOT / settings()["paths"][kind] / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
