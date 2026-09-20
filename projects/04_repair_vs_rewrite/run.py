"""Given failing code, is it better to patch it or start over?

Agents almost always patch. Shown a failure, they send the broken code back with the error
and ask for a fix. The alternative - throw it away and regenerate from the task description
- is rarely tried, and the comparison is rarely made.

It should be, because the two have different costs and different failure modes. Repair
sends the broken code back in the prompt, so it costs more tokens *and* anchors the model
on an approach that already failed. Rewrite is cheaper per call and unanchored, but throws
away whatever the first attempt got right.

Both arms start from the same failed attempt and get exactly one more call, so the
comparison is like for like.

    python run.py --limit 200
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.datasets import load  # noqa: E402
from shared.execute import extract_code, run  # noqa: E402
from shared.model import available, generate  # noqa: E402

HERE = Path(__file__).resolve().parent

FIRST = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""

REPAIR = """This Python function is wrong.

Task: {prompt}

Your code:
```python
{code}
```

Running the tests gave:
{error}

Fix it. Output ONLY the corrected function and any imports it needs. No explanation.
"""

REWRITE = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

A previous attempt failed. Take a different approach.
Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1

    tasks = load("mbpp", args.limit)
    print(f"mbpp: {len(tasks)} tasks, model {args.model}\n")

    print("  first attempt...")
    failed = []
    t0 = time.time()
    for i, task in enumerate(tasks, 1):
        raw = generate(
            FIRST.format(prompt=task.prompt, test=task.tests[0]),
            model=args.model,
            temperature=0.0,
        )
        code = extract_code(raw) if raw else ""
        o = run(code, list(task.tests), task.setup)
        if not o.passed:
            failed.append((task, code, o.detail))
        if i % 100 == 0 or i == len(tasks):
            print(f"    {i}/{len(tasks)}", flush=True)
    print(
        f"  first-attempt pass@1: {(len(tasks) - len(failed)) / len(tasks):.1%}  "
        f"({len(failed)} failures to work with)  [{time.time() - t0:.0f}s]"
    )
    if not failed:
        print("nothing failed; nothing to compare")
        return 1

    results = {"repair": 0, "rewrite": 0, "both": 0, "neither": 0}
    per_task = []
    for i, (task, code, err) in enumerate(failed, 1):
        rp = generate(
            REPAIR.format(prompt=task.prompt, code=code, error=err or "the tests failed"),
            model=args.model,
            temperature=0.0,
            seed=1,
        )
        rw = generate(
            REWRITE.format(prompt=task.prompt, test=task.tests[0]),
            model=args.model,
            temperature=0.0,
            seed=2,
        )
        r_ok = run(extract_code(rp or ""), list(task.tests), task.setup).passed
        w_ok = run(extract_code(rw or ""), list(task.tests), task.setup).passed
        results["repair"] += r_ok
        results["rewrite"] += w_ok
        if r_ok and w_ok:
            results["both"] += 1
        elif not r_ok and not w_ok:
            results["neither"] += 1
        per_task.append({"task_id": task.task_id, "repair": r_ok, "rewrite": w_ok})
        if i % 50 == 0 or i == len(failed):
            print(f"    second attempt {i}/{len(failed)}", flush=True)

    f = len(failed)
    only_r = results["repair"] - results["both"]
    only_w = results["rewrite"] - results["both"]
    print("\n" + "=" * 68)
    print(f"REPAIR vs REWRITE - {f} failed first attempts, one retry each")
    print("=" * 68)
    print(f"  repair  fixed : {results['repair']:4}  ({results['repair'] / f:6.1%})")
    print(f"  rewrite fixed : {results['rewrite']:4}  ({results['rewrite'] / f:6.1%})")
    print(f"  difference    : {(results['repair'] - results['rewrite']) / f:+.1%}")
    print()
    print(f"  both worked   : {results['both']:4}  ({results['both'] / f:6.1%})")
    print(f"  only repair   : {only_r:4}  ({only_r / f:6.1%})")
    print(f"  only rewrite  : {only_w:4}  ({only_w / f:6.1%})")
    print(f"  neither       : {results['neither']:4}  ({results['neither'] / f:6.1%})")
    union = results["both"] + only_r + only_w
    print(
        f"\n  Trying both fixes {union / f:.1%} - "
        f"{(union - max(results['repair'], results['rewrite'])) / f:+.1%} over the better "
        "single strategy, for twice the calls."
    )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                "model": args.model,
                "tasks": len(tasks),
                "first_attempt_failures": f,
                "repair_fixed": results["repair"],
                "rewrite_fixed": results["rewrite"],
                "both": results["both"],
                "neither": results["neither"],
                "per_task": per_task,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
