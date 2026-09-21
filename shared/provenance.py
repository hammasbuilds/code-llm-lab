"""The block of metadata every result file needs to be reproducible.

A results file that says `pass@1: 76.0%` and nothing else is a number, not a measurement.
Six months later nobody can tell which model produced it, how many tasks it saw, or whether
it was a real run or the smoke test that wrote the same filename - which is exactly the
confusion that nearly shipped an n=4 result as if it were n=60.

So every project stamps the same block: what ran it, against what, at what size, with what
sampling settings, and when.
"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Any


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def stamp(
    *,
    models: str | list[str],
    benchmark: str,
    n: int,
    temperature: float | list[float] = 0.0,
    samples: int = 1,
    seeds: Any = None,
    extra: dict | None = None,
) -> dict:
    """The provenance block to merge into a results dict.

    `n` is the sample size the run actually completed, not the requested limit - a run cut
    short should not claim the size it was asked for.
    """
    return {
        "models": [models] if isinstance(models, str) else list(models),
        "benchmark": benchmark,
        "n": n,
        "temperature": temperature,
        "samples": samples,
        "seeds": seeds,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "commit": _git_commit(),
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        **(extra or {}),
    }
