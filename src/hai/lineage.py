"""Append-only provenance log: every step records its inputs, outputs and parameters."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT


def _git_rev() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "uncommitted"


def _rel(p) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except (ValueError, OSError):
        return str(p)  # URLs and database tables


def record(step: str, inputs: list, outputs: list, **params) -> None:
    entry = {
        "step": step,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_version": _git_rev(),
        "inputs": [_rel(i) for i in inputs],
        "outputs": [_rel(o) for o in outputs],
        "params": params,
    }
    log = ROOT / "metadata" / "lineage.jsonl"
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[lineage] {step}: {len(outputs)} output(s)")
