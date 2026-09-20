"""Model-written tests, scored by what they catch rather than what they cover.

"Write tests for this" is one of the most common things people ask a coder model, and the
usual way to judge the answer is coverage. Coverage is a bad judge: a test that calls every
line and asserts nothing scores 100%.

So score the tests the way mutation testing does. Take the reference solution, break it in
one place, and ask whether the tests notice. A suite that cannot tell the reference from a
program with a flipped comparison has not tested the comparison, whatever its coverage says.

Two arms, because the first attempt at this failed in an informative way.

**`from_description`** - the model sees only MBPP's task sentence, as a developer working
from a ticket would. Almost none of these suites pass the reference solution. Not because
the tests are bad, but because the sentence does not say whether the function returns a
list or a tuple, or what it does with empty input, and the model has to guess. The validity
rate of this arm is a measurement of how underspecified the descriptions are.

**`from_code`** - the model sees the implementation, as a developer adding tests to existing
code would. These suites do pass the reference, which makes their kill rate measurable, and
that kill rate is the number the project is actually about.

Comparing them separates two things that get conflated when people complain about generated
tests: whether the *spec* was good enough, and whether the *tests* were.

    python run.py --limit 150
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.datasets import load  # noqa: E402
from shared.execute import extract_code, run_many  # noqa: E402
from shared.model import available, generate_many  # noqa: E402

HERE = Path(__file__).resolve().parent
# Reuse the mutation engine next door rather than writing a second one.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mbpp-false-accepts" / "src"))

FROM_DESCRIPTION = """Write assert statements that test this Python function thoroughly.

Task: {prompt}

The function is called `{entry}`.

Rules:
- Output ONLY assert statements, one per line.
- Cover edge cases: empty input, boundaries, zero, negatives, single elements.
- Do not redefine the function. Do not import anything. No explanation.
"""

FROM_CODE = """Write assert statements that test this Python function thoroughly.

```python
{code}
```

Rules:
- Output ONLY assert statements, one per line, calling `{entry}`.
- The assertions must match what this code actually does.
- Cover edge cases: empty input, boundaries, zero, negatives, single elements.
- Do not redefine the function. Do not import anything. No explanation.
"""

ARMS = {"from_description": FROM_DESCRIPTION, "from_code": FROM_CODE}

_ASSERT = re.compile(r"^\s*assert\s+")


def parse_asserts(raw: str, limit: int = 20) -> list[str]:
    """Keep the assert lines that are individually valid Python.

    A model asked for asserts still writes prose, so the lines are filtered. More
    importantly the *last* assert is often truncated by the token limit - `assert f([1,`
    - and one unclosed bracket makes the whole suite a SyntaxError, which would be scored
    as "this suite rejects the reference" and silently drop the task from the sample.
    Parsing each line on its own keeps the good ones and discards only the broken tail.
    """
    out: list[str] = []
    for line in extract_code(raw).splitlines():
        line = line.strip()
        if not _ASSERT.match(line) or line in out:
            continue
        try:
            ast.parse(line)
        except SyntaxError:
            continue
        out.append(line)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=8)
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

    summary: dict[str, dict] = {}
    for arm, template in ARMS.items():
        print(f"  generating suites: {arm}")
        t0 = time.time()
        raws = generate_many(
            [
                template.format(prompt=t.prompt, entry=t.entry_point, code=t.reference)
                for t in tasks
            ],
            model=args.model,
            temperature=0.0,
            workers=args.workers,
            progress=arm,
        )
        suites = {t.task_id: parse_asserts(r or "") for t, r in zip(tasks, raws, strict=True)}
        print(f"    {len(tasks)} suites in {time.time() - t0:.0f}s", flush=True)

        # A suite that rejects the reference is wrong, not strict. Only valid suites can
        # have a meaningful kill rate, so validity is reported first and separately.
        checks = run_many([(t.reference, suites[t.task_id], t.setup) for t in tasks], args.workers)
        valid = [t for t, o in zip(tasks, checks, strict=True) if o.passed and suites[t.task_id]]
        print(
            f"    suites that pass the reference: {len(valid)}/{len(tasks)}"
            f"  ({len(valid) / len(tasks):.1%})"
        )

        rows = []
        for task in valid:
            muts = mutants(task.reference, limit=args.per_problem)
            if not muts:
                continue
            model_out = run_many(
                [(m.code, suites[task.task_id], task.setup) for m in muts], args.workers
            )
            bench_out = run_many(
                [(m.code, list(task.tests), task.setup) for m in muts], args.workers
            )
            rows.append(
                {
                    "task_id": task.task_id,
                    "asserts": len(suites[task.task_id]),
                    "mutants": len(muts),
                    "model_killed": sum(1 for o in model_out if not o.passed),
                    "mbpp_killed": sum(1 for o in bench_out if not o.passed),
                }
            )

        summary[arm] = {
            "suites": len(tasks),
            "valid": len(valid),
            "validity": len(valid) / len(tasks),
            "scored": len(rows),
            "mutants": sum(r["mutants"] for r in rows),
            "model_killed": sum(r["model_killed"] for r in rows),
            "mbpp_killed": sum(r["mbpp_killed"] for r in rows),
            "mean_asserts": (sum(r["asserts"] for r in rows) / len(rows) if rows else 0.0),
            "per_task": rows,
        }
        print()

    print("=" * 68)
    print(f"MODEL-WRITTEN TESTS - {len(tasks)} MBPP tasks, {args.model}")
    print("=" * 68)
    print(f"  {'':18} {'valid':>8} {'scored':>8} {'asserts':>9} {'kill rate':>11}")
    for arm, s in summary.items():
        kr = s["model_killed"] / s["mutants"] if s["mutants"] else 0.0
        print(
            f"  {arm:18} {s['validity']:8.1%} {s['scored']:8} {s['mean_asserts']:9.1f} {kr:11.1%}"
        )

    fc = summary.get("from_code", {})
    if fc.get("mutants"):
        kr = fc["model_killed"] / fc["mutants"]
        bench = fc["mbpp_killed"] / fc["mutants"]
        print(f"\n  On the suites that are valid ({fc['scored']} tasks, {fc['mutants']} mutants):")
        print(f"    model-written kill rate : {kr:6.1%}  {'#' * round(40 * kr)}")
        print(f"    MBPP's own kill rate    : {bench:6.1%}  {'#' * round(40 * bench)}")
        print(f"    difference              : {kr - bench:+.1%}")
        print(
            f"\n  The model wrote {fc['mean_asserts'] / 3.0:.1f}x as many asserts as MBPP "
            f"ships, and caught {kr - bench:+.1%} more."
        )

    fd = summary.get("from_description", {})
    if fd:
        print(
            f"\n  Working from the task description alone, only {fd['validity']:.1%} of suites\n"
            "  even agree with the reference - the descriptions do not say whether the\n"
            "  function returns a list or a tuple, or what empty input should do. That is a\n"
            "  measurement of the spec, not of the model."
        )

    (HERE / "results.json").write_text(
        json.dumps({"model": args.model, "n_tasks": len(tasks), "arms": summary}, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
