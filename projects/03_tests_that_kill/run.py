"""Model-written tests, scored by what they catch rather than what they cover.

"Write tests for this function" is one of the most common things people ask a coder model
to do, and the usual way to judge the result is coverage. Coverage is a bad judge: a test
that calls every line and asserts nothing scores 100%.

So score the tests the way mutation testing does. Take the reference solution, break it in
one place, and ask whether the model's tests notice. A test suite that cannot tell the
reference from a program with a flipped comparison has not tested the comparison, whatever
its coverage says.

Two numbers per suite:

- **kill rate** - the share of mutants the suite rejects. This is the real measure.
- **validity**  - does the suite pass the *correct* code? A suite that fails everything
  kills every mutant and is worthless, so kill rate without this is meaningless.

Only suites that pass the reference are scored, which is the honest denominator.

    python run.py --limit 120
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
from shared.execute import extract_code, run_many  # noqa: E402
from shared.model import available, generate  # noqa: E402

HERE = Path(__file__).resolve().parent
# Reuse the mutation engine next door rather than writing a second one.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mbpp-false-accepts" / "src"))

PROMPT = """Write assert statements that test this Python function thoroughly.

Task: {prompt}

The function is called `{entry}`.

Rules:
- Output ONLY assert statements, one per line.
- Cover edge cases: empty input, boundaries, zero, negatives, single elements.
- Do not redefine the function. Do not import anything. No explanation.
"""

_ASSERT = re.compile(r"^\s*assert\s+")


def parse_asserts(raw: str, limit: int = 20) -> list[str]:
    """Keep only the assert lines; a model asked for asserts still writes prose."""
    out = []
    for line in extract_code(raw).splitlines():
        line = line.strip()
        if _ASSERT.match(line) and line not in out:
            out.append(line)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--per-problem", type=int, default=8, help="mutants per task")
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1
    try:
        from mutate import mutants
    except ImportError:
        print("needs the mutation engine from ../mbpp-false-accepts/src/mutate.py")
        return 1

    tasks = [t for t in load("mbpp", args.limit) if t.entry_point]
    print(f"mbpp: {len(tasks)} tasks, model {args.model}\n")

    print("  generating test suites...")
    suites: dict[str, list[str]] = {}
    t0 = time.time()
    for i, task in enumerate(tasks, 1):
        raw = generate(
            PROMPT.format(prompt=task.prompt, entry=task.entry_point),
            model=args.model,
            temperature=0.0,
        )
        suites[task.task_id] = parse_asserts(raw or "")
        if i % 50 == 0 or i == len(tasks):
            rate = (time.time() - t0) / i
            print(f"    {i}/{len(tasks)}  eta {rate * (len(tasks) - i) / 60:.0f} min", flush=True)

    # A suite that rejects the reference is broken, not strict. Score only valid ones.
    valid_checks = run_many(
        [(t.reference, suites[t.task_id], t.setup) for t in tasks], args.workers
    )
    valid = [t for t, o in zip(tasks, valid_checks, strict=True) if o.passed and suites[t.task_id]]
    empty = sum(1 for t in tasks if not suites[t.task_id])
    print(
        f"\n  suites that pass the reference: {len(valid)}/{len(tasks)}"
        f"  ({len(valid) / len(tasks):.1%})   [{empty} were empty]"
    )

    rows = []
    for task in valid:
        muts = mutants(task.reference, limit=args.per_problem)
        if not muts:
            continue
        model_out = run_many(
            [(m.code, suites[task.task_id], task.setup) for m in muts], args.workers
        )
        bench_out = run_many([(m.code, list(task.tests), task.setup) for m in muts], args.workers)
        rows.append(
            {
                "task_id": task.task_id,
                "asserts": len(suites[task.task_id]),
                "mutants": len(muts),
                "model_killed": sum(1 for o in model_out if not o.passed),
                "mbpp_killed": sum(1 for o in bench_out if not o.passed),
            }
        )

    if not rows:
        print("nothing scored")
        return 1

    mm = sum(r["model_killed"] for r in rows)
    bb = sum(r["mbpp_killed"] for r in rows)
    tot = sum(r["mutants"] for r in rows)
    mean_asserts = sum(r["asserts"] for r in rows) / len(rows)

    print("\n" + "=" * 68)
    print("KILL RATE - what the tests actually catch")
    print("=" * 68)
    print(f"  tasks scored        : {len(rows)}")
    print(f"  mutants             : {tot}")
    print(f"  asserts per suite   : model {mean_asserts:.1f}   MBPP 3.0")
    print()
    print(f"  model-written kill rate : {mm / tot:6.1%}  {'#' * round(40 * mm / tot)}")
    print(f"  MBPP's own kill rate    : {bb / tot:6.1%}  {'#' * round(40 * bb / tot)}")
    print(f"  difference              : {(mm - bb) / tot:+.1%}")
    print(f"\n  The model wrote {mean_asserts / 3.0:.1f}x as many asserts as MBPP ships.")
    both = sum(1 for r in rows if r["model_killed"] == r["mutants"])
    none = sum(1 for r in rows if r["model_killed"] == 0)
    print(f"  suites killing every mutant : {both} ({both / len(rows):.1%})")
    print(f"  suites killing none         : {none} ({none / len(rows):.1%})")

    (HERE / "results.json").write_text(
        json.dumps(
            {
                "model": args.model,
                "tasks_scored": len(rows),
                "mutants": tot,
                "model_kill_rate": mm / tot,
                "mbpp_kill_rate": bb / tot,
                "mean_asserts_model": mean_asserts,
                "per_task": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
