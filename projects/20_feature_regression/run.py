"""Add a requirement. Does what already worked still work?

This is the ordinary shape of software work and almost nothing in a code benchmark covers
it. The function exists, it passes, and now it has to do one more thing. The risk is not
that the new requirement is hard - it is that satisfying it quietly breaks the behaviour
nobody mentioned, because nobody mentioned it.

Start from solutions that pass. Ask for one added requirement. Then run **the original
tests** again.

Those tests say nothing about the new feature, so they can only fail one way: the model
changed behaviour it was not asked to change. That makes regression directly measurable
without a judge and without writing new tests for the new behaviour.

Four requests, ordered by how far they reach into the existing code:

- `validate`  - raise ValueError on invalid input
- `default`   - add an optional parameter with a default
- `logging`   - log the inputs and the result
- `generalise`- make it work for one more input type

`default` is the interesting one. Adding an optional parameter with a default is the textbook
backwards-compatible change - if anything regresses there, it regressed for no reason at all.

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

CHANGES = {
    "validate": "Also raise a ValueError with a clear message if the input is invalid.",
    "default": "Also accept an optional second parameter `verbose` defaulting to False. "
    "When it is True, the behaviour is unchanged but the function also prints its result.",
    "logging": "Also log the arguments and the return value using the `logging` module.",
    "generalise": "Also make it accept a tuple wherever it currently accepts a list, "
    "behaving the same way.",
}

PROMPT = """Here is a working Python function.

```python
{code}
```

Add this requirement:
{change}

Everything the function already does must keep working exactly as before.

Output ONLY the updated function and any imports it needs. No explanation, no tests.
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

    print("  working solutions to extend (cached from project 01)...")
    t0 = time.time()
    sols = solve(tasks, model=args.model, workers=args.workers)
    working = [s for s in sols if s.passed]
    print(f"  {len(working)}/{len(sols)} pass and are eligible  [{time.time() - t0:.0f}s]\n")

    if not working:
        print("no working solutions - nothing to extend")
        return 1

    summary: dict[str, dict] = {}
    broke_under: dict[str, set[str]] = {}

    for name, change in CHANGES.items():
        t0 = time.time()
        raws = generate_many(
            [PROMPT.format(code=s.code, change=change) for s in working],
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
        kinds: dict[str, int] = {}
        for o in outs:
            if not o.passed:
                kinds[o.status] = kinds.get(o.status, 0) + 1
        summary[name] = {
            "n": len(working),
            "regressed": len(broke),
            "regression_rate": len(broke) / len(working),
            "failure_kinds": kinds,
        }
        print(
            f"  {name:11} regressed {len(broke):4}/{len(working)} "
            f"({len(broke) / len(working):6.1%})  {kinds}  [{time.time() - t0:.0f}s]"
        )

    print("\n" + "=" * 76)
    print(f"FEATURE REGRESSION - {len(working)} working solutions, {args.model}")
    print("=" * 76)
    for name in CHANGES:
        r = summary[name]["regression_rate"]
        print(f"  {name:12} {r:6.1%}  {'#' * round(55 * r)}")

    rates = {k: v["regression_rate"] for k, v in summary.items()}
    safest, riskiest = min(rates, key=rates.get), max(rates, key=rates.get)
    print(f"\n  safest change  : {safest} at {rates[safest]:.1%}")
    print(f"  riskiest change: {riskiest} at {rates[riskiest]:.1%}")

    d = rates["default"]
    print(
        f"\n  Adding an optional parameter with a default regressed {d:.1%} of functions.\n"
        "  That change cannot break a caller by construction - the old call signature and\n"
        "  the old behaviour are both still valid - so every one of those is the model\n"
        "  rewriting something it was asked to leave alone."
    )

    ever = set().union(*broke_under.values())
    always = set.intersection(*broke_under.values()) if broke_under else set()
    print(
        f"\n  regressed under at least one change : {len(ever):4} ({len(ever) / len(working):.1%})"
    )
    print(
        f"  regressed under every change        : {len(always):4} "
        f"({len(always) / len(working):.1%})"
    )
    print(
        "\n  The original tests say nothing about the new requirement, so they can only\n"
        "  fail by the model changing behaviour nobody asked it to change."
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
                "changes": summary,
                "regressed_under_any": len(ever),
                "regressed_under_all": len(always),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
