"""MBPP and HumanEval, loaded from the local Hugging Face cache.

Both benchmarks describe a task, give a reference solution and give a way to check a
candidate. They disagree about almost everything else - MBPP hands you three asserts and
a plain-English sentence, HumanEval hands you a function signature with a docstring and a
`check()` harness - so the loader normalises them into one shape and every project here
runs against both without caring which is which.

No network. Both are already cached and together weigh about 1 MB.
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

_CALLED = re.compile(r"assert\s+(?:not\s+)?([A-Za-z_]\w*)\s*\(")

# MBPP ships an official split by task_id (Austin et al. 2021), and it matters more here
# than a split usually does. Nothing in this repo trains anything - but qwen2.5-coder was
# pretrained on public code, and tasks 601-974 have been public MBPP *training* data since
# 2021. Measured on this model they are 8.4 points easier than the held-out test split
# (85.2% vs 76.8%, p=0.002), so a run over all 974 reports a number inflated by the share
# of training data in it, and is not comparable to any published MBPP figure.
MBPP_SPLITS = {
    "prompt": (1, 10),  # the few-shot examples the paper prompts with
    "test": (11, 510),  # what "MBPP pass@1" means in published work
    "validation": (511, 600),
    "train": (601, 974),  # public since 2021; treat results here as contaminated
    "all": (1, 974),
}


@dataclass(frozen=True)
class Task:
    """One problem, normalised across benchmarks."""

    benchmark: str  # "mbpp" | "humaneval"
    task_id: str
    prompt: str  # what the model is asked to implement
    reference: str  # the solution the benchmark calls correct
    entry_point: str  # the function under test
    tests: tuple[str, ...]  # assert statements, or a single check() call
    setup: str = ""  # runs after the solution, before the tests

    @property
    def is_mbpp(self) -> bool:
        return self.benchmark == "mbpp"


def _cache_roots() -> list[Path]:
    roots = []
    if env := os.environ.get("HF_HUB_CACHE"):
        roots.append(Path(env))
    if env := os.environ.get("HF_HOME"):
        roots.append(Path(env) / "hub")
    roots.append(Path.home() / ".cache" / "huggingface" / "hub")
    return roots


def _find(pattern: str) -> Path | None:
    for root in _cache_roots():
        hits = sorted(glob.glob(str(root / pattern)))
        if hits:
            return Path(hits[0])
    return None


def load_mbpp(limit: int | None = None, split: str = "all") -> list[Task]:
    """MBPP, optionally restricted to one of its official splits.

    The default stays `all` so existing results remain reproducible, but `test` is the
    honest default for any number meant to be compared with published work - see
    `MBPP_SPLITS` for why the difference is not cosmetic.
    """
    if split not in MBPP_SPLITS:
        raise ValueError(f"unknown mbpp split {split!r}; expected one of {sorted(MBPP_SPLITS)}")
    lo, hi = MBPP_SPLITS[split]
    path = _find("datasets--Muennighoff--mbpp/snapshots/*/data/mbpp.jsonl")
    if path is None:
        raise FileNotFoundError("MBPP not in the local Hugging Face cache")
    out: list[Task] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if not lo <= int(r["task_id"]) <= hi:
            continue
        tests = tuple(r["test_list"])
        entry = next((m.group(1) for t in tests if (m := _CALLED.search(t))), "")
        if not entry:
            continue
        out.append(
            Task(
                benchmark="mbpp",
                task_id=f"mbpp/{r['task_id']}",
                prompt=r["text"],
                reference=r["code"],
                entry_point=entry,
                tests=tests,
                setup=r.get("test_setup_code") or "",
            )
        )
        if limit and len(out) >= limit:
            break
    return out


def load_humaneval(limit: int | None = None) -> list[Task]:
    path = _find("datasets--openai--openai_humaneval/snapshots/*/openai_humaneval/*.parquet")
    if path is None:
        raise FileNotFoundError("HumanEval not in the local Hugging Face cache")
    import pandas as pd

    frame = pd.read_parquet(path)
    out: list[Task] = []
    for _, row in frame.iterrows():
        out.append(
            Task(
                benchmark="humaneval",
                task_id=row["task_id"],
                # The prompt IS the signature plus docstring; that is the task statement.
                prompt=row["prompt"],
                reference=row["prompt"] + row["canonical_solution"],
                entry_point=row["entry_point"],
                # HumanEval ships one `check(fn)` harness rather than loose asserts.
                tests=(row["test"], f"check({row['entry_point']})"),
            )
        )
        if limit and len(out) >= limit:
            break
    return out


def load(benchmark: str = "mbpp", limit: int | None = None, split: str = "all") -> list[Task]:
    if benchmark == "mbpp":
        return load_mbpp(limit, split)
    if benchmark == "humaneval":
        # HumanEval has no splits: all 164 problems are held out, which is one reason it
        # is the cleaner comparison and why `split` is rejected rather than ignored here.
        if split not in ("all", "test"):
            raise ValueError(f"humaneval has no {split!r} split; it is 164 held-out problems")
        return load_humaneval(limit)
    raise ValueError(f"unknown benchmark {benchmark!r}; expected mbpp or humaneval")


if __name__ == "__main__":
    for b in ("mbpp", "humaneval"):
        ts = load(b)
        print(f"{b:10} {len(ts):4} tasks | entry points {sum(1 for t in ts if t.entry_point)}")
        t = ts[0]
        print(f"  {t.task_id}  {t.entry_point}  tests={len(t.tests)}")
