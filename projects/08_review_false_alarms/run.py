"""Code review: it catches bugs, but how often does it cry wolf?

Every AI review tool reports how many real bugs it found. Almost none report how often it
flagged code that was fine - and that second number is the one that decides whether anyone
keeps the tool switched on. A reviewer that flags a third of clean diffs gets muted in a
week, however good its catches are.

Three arms, all reviewed with the identical prompt, so the only thing that varies is what
the code actually is:

- `buggy`     - solutions this model wrote that FAIL their tests. A flag here is a catch.
- `passing`   - solutions this model wrote that PASS their tests.
- `reference` - MBPP's own human-written reference solutions.

Two clean arms on purpose. Model-written passing code and human-written reference code are
both "fine", but they are fine in different ways, and a reviewer might well treat them
differently. Reporting one would hide that.

**A flag on test-passing code is not automatically wrong.** MBPP specifies each problem with
three asserts, and three asserts accept a lot of broken code - see mbpp-false-accepts, where
29% of problems accept a provably wrong program. So a flag on passing code is scored as a
false alarm here while being, sometimes, a real catch the tests missed. That is a ceiling on
what this measurement can claim, and it is stated rather than smoothed over.

    python run.py --limit 250
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.datasets import load  # noqa: E402
from shared.model import available, generate_many  # noqa: E402
from shared.provenance import stamp  # noqa: E402
from shared.solutions import solve  # noqa: E402

HERE = Path(__file__).resolve().parent

REVIEW = """You are reviewing a Python function before it is merged.

Task it is supposed to do:
{prompt}

Code:
```python
{code}
```

Does this code have a bug that would make it fail the task?

Answer with exactly two lines:
VERDICT: BUG
REASON: <one line>

or:

VERDICT: OK
REASON: <one line>
"""

_VERDICT = re.compile(r"VERDICT\s*:\s*(BUG|OK)\b", re.I)


def parse_verdict(raw: str | None) -> str | None:
    """`BUG`, `OK`, or None when the model did not answer in the required shape.

    Unparseable answers are kept as their own category rather than folded into `OK`. A
    reviewer that rambles instead of deciding has not approved the code, and counting it
    as an approval would flatter the false-alarm rate - which is the number this project
    exists to measure.
    """
    if not raw:
        return None
    m = _VERDICT.search(raw)
    return m.group(1).upper() if m else None


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

    print("  generating the code to be reviewed (cached from project 01)...")
    t0 = time.time()
    sols = solve(tasks, model=args.model, workers=args.workers)
    buggy = [s for s in sols if not s.passed]
    passing = [s for s in sols if s.passed]
    print(f"  {len(passing)} pass, {len(buggy)} fail  [{time.time() - t0:.0f}s]\n")

    if not buggy:
        print("no failing solutions to review - nothing to measure")
        return 1

    arms: dict[str, list[tuple[str, str]]] = {
        "buggy": [(s.task.prompt, s.code) for s in buggy],
        "passing": [(s.task.prompt, s.code) for s in passing],
        "reference": [(t.prompt, t.reference) for t in tasks],
    }

    results: dict[str, dict] = {}
    for arm, items in arms.items():
        t0 = time.time()
        raws = generate_many(
            [REVIEW.format(prompt=p, code=c) for p, c in items],
            model=args.model,
            temperature=0.0,
            workers=args.workers,
            num_predict=128,
            progress=arm,
        )
        verdicts = [parse_verdict(r) for r in raws]
        n = len(verdicts)
        flagged = sum(v == "BUG" for v in verdicts)
        cleared = sum(v == "OK" for v in verdicts)
        unparsed = sum(v is None for v in verdicts)
        results[arm] = {
            "n": n,
            "flagged": flagged,
            "cleared": cleared,
            "unparsed": unparsed,
            "flag_rate": flagged / n if n else 0.0,
        }
        print(
            f"  {arm:10} n={n:4}  flagged {flagged:4} ({flagged / n:6.1%})  "
            f"cleared {cleared:4}  unparsed {unparsed:3}  [{time.time() - t0:.0f}s]"
        )

    b, p, r = results["buggy"], results["passing"], results["reference"]
    recall = b["flag_rate"]

    print("\n" + "=" * 72)
    print(f"REVIEW FALSE ALARMS - {len(tasks)} MBPP tasks, {args.model}")
    print("=" * 72)
    print(f"  caught, of code that really is broken : {recall:6.1%}  (n={b['n']})")
    print(f"  flagged, of model code that passes    : {p['flag_rate']:6.1%}  (n={p['n']})")
    print(f"  flagged, of MBPP's own references     : {r['flag_rate']:6.1%}  (n={r['n']})")

    # Precision if you acted on the verdicts, against the passing arm as the negatives.
    tp, fp = b["flagged"], p["flagged"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    print(f"\n  precision, if you acted on every flag : {precision:6.1%}")
    print(f"  ({tp} real bugs among {tp + fp} flags raised)")

    if p["n"]:
        per_catch = fp / tp if tp else float("inf")
        print(f"  false alarms per real bug caught      : {per_catch:6.2f}")

    print(
        "\n  A flag on passing code is scored as a false alarm here. Some of those are\n"
        "  real catches MBPP's three asserts missed - which bounds this number rather\n"
        "  than invalidating it."
    )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(models=args.model, benchmark="mbpp", n=len(tasks)),
                "arms": results,
                "recall_on_buggy": recall,
                "false_alarm_rate_passing": p["flag_rate"],
                "false_alarm_rate_reference": r["flag_rate"],
                "precision": precision,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
