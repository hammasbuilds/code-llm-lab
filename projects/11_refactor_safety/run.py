"""Does the refactor keep the tests green?

"Clean this up", "add type hints", "make it more Pythonic" - these are the requests people
hand an AI assistant most readily, because they feel safe. Nothing is being *added*, so
nothing should break.

A refactor has a property the other requests in this repo do not: **it has a correct answer
that is already known.** The code works. Any refactor that changes observable behaviour is
wrong, whatever it looks like, and the original tests say so without needing a judge.

Four requests, each on the same set of working solutions:

- `typehints`  - add type annotations, change nothing else
- `rename`     - give the variables descriptive names
- `extract`    - pull a piece out into a helper function
- `idiomatic`  - rewrite it to be more Pythonic

They are ordered roughly by how much licence each one grants. `typehints` should be nearly
free; `idiomatic` is an open invitation to rewrite. If the breakage rate tracks that
ordering, the lesson is about how much freedom to give the request - which is something a
person can act on.

Only solutions that already pass are refactored, so a failure afterwards is breakage the
refactor caused and not a bug it inherited.

    python run.py --limit 250
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.datasets import load  # noqa: E402
from shared.execute import extract_code, run_many  # noqa: E402
from shared.model import available, generate_many  # noqa: E402
from shared.provenance import stamp  # noqa: E402
from shared.solutions import solve  # noqa: E402

HERE = Path(__file__).resolve().parent

REFACTORS = {
    "typehints": "Add type annotations to the parameters and the return value. "
    "Change nothing else about the code.",
    "rename": "Rename the local variables to descriptive names. "
    "Change nothing else about the code.",
    "extract": "Extract part of this function into a separate helper function, "
    "keeping the original function's name and signature.",
    "idiomatic": "Rewrite this to be more Pythonic and idiomatic.",
}

PROMPT = """Refactor this Python function.

{instruction}

The behaviour must not change.

```python
{code}
```

Output ONLY the resulting code - the function and any imports or helpers it needs.
No explanation, no tests.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1

    tasks = load("mbpp", args.limit)
    print(f"mbpp: {len(tasks)} tasks, model {args.model}\n")

    print("  generating the code to refactor (cached from project 01)...")
    t0 = time.time()
    sols = solve(tasks, model=args.model, workers=args.workers)
    working = [s for s in sols if s.passed]
    print(f"  {len(working)}/{len(sols)} pass and are eligible  [{time.time() - t0:.0f}s]\n")

    if not working:
        print("no working solutions to refactor - nothing to measure")
        return 1

    summary: dict[str, dict] = {}
    broke_under: dict[str, set[str]] = {}

    for name, instruction in REFACTORS.items():
        t0 = time.time()
        raws = generate_many(
            [PROMPT.format(instruction=instruction, code=s.code) for s in working],
            model=args.model,
            temperature=0.0,
            workers=args.workers,
            progress=name,
        )
        codes = [extract_code(r) if r else "" for r in raws]
        outs = run_many(
            [(c, list(s.task.tests), s.task.setup) for c, s in zip(codes, working, strict=True)],
            args.workers,
        )
        broke = {s.task.task_id for s, o in zip(working, outs, strict=True) if not o.passed}
        broke_under[name] = broke
        # How the breakage happened matters: a crash is a different failure from a
        # silently changed answer, and only the second survives a smoke test.
        kinds: dict[str, int] = {}
        for o in outs:
            if not o.passed:
                kinds[o.status] = kinds.get(o.status, 0) + 1
        mean_len = sum(len(c) for c in codes) / len(codes)
        summary[name] = {
            "n": len(working),
            "broke": len(broke),
            "break_rate": len(broke) / len(working),
            "failure_kinds": kinds,
            "mean_chars": mean_len,
            "mean_chars_before": sum(len(s.code) for s in working) / len(working),
        }
        print(
            f"  {name:10} broke {len(broke):4}/{len(working)} "
            f"({len(broke) / len(working):6.1%})  {kinds}  [{time.time() - t0:.0f}s]"
        )

    print("\n" + "=" * 72)
    print(f"REFACTOR SAFETY - {len(working)} working solutions, {args.model}")
    print("=" * 72)
    for name in REFACTORS:
        s = summary[name]
        print(f"  {name:11} {s['break_rate']:6.1%}  {'#' * round(60 * s['break_rate'])}")

    rates = {k: v["break_rate"] for k, v in summary.items()}
    safest, riskiest = min(rates, key=rates.get), max(rates, key=rates.get)
    print(f"\n  safest   : {safest} at {rates[safest]:.1%}")
    print(f"  riskiest : {riskiest} at {rates[riskiest]:.1%}")
    print(f"  spread   : {rates[riskiest] - rates[safest]:.1%}")

    ever = set().union(*broke_under.values())
    always = set.intersection(*broke_under.values()) if broke_under else set()
    print(f"\n  broke under at least one refactor : {len(ever):4} ({len(ever) / len(working):.1%})")
    print(
        f"  broke under every refactor        : {len(always):4} ({len(always) / len(working):.1%})"
    )
    print(
        "  <- the second group is code that was fragile to begin with; the gap between\n"
        "     them is what the choice of refactor is actually worth."
    )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(
                    models=args.model,
                    benchmark="mbpp",
                    n=len(tasks),
                    extra={"eligible": len(working)},
                ),
                "refactors": summary,
                "broke_under_any": len(ever),
                "broke_under_all": len(always),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
