"""How much of the repair comes from the error message?

Project 02 showed a self-debug loop is worth two rounds and no more. It varied *how many*
times the model saw the failure. This varies *what it saw* - and that is the part a person
building an agent actually controls.

The decision is concrete. A harness has to choose what to put back in the prompt, and the
options cost different amounts of context:

- `nothing`   - "that was wrong, try again". The cheapest possible signal.
- `boolean`   - the tests failed, no detail.
- `assertion` - the assert that failed and nothing else.
- `traceback` - the full traceback, exception type and line.
- `expected`  - the failing assert plus what it produced instead.

If `traceback` and `nothing` land in the same place, then the loop is not reading the error
at all - it is just being asked again, and every byte of captured stderr is wasted context.
That is a cheap thing to know before building the plumbing to collect it.

Every arm starts from the **same** failed first attempt, so the only variable is the
feedback. One retry each, because project 02 established that later rounds add nothing.

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
from shared.execute import extract_code, run, run_many  # noqa: E402
from shared.model import available, generate_many  # noqa: E402
from shared.provenance import stamp  # noqa: E402
from shared.solutions import solve  # noqa: E402

HERE = Path(__file__).resolve().parent

RETRY = """This Python function is wrong.

Task: {prompt}

Your code:
```python
{code}
```
{feedback}
Fix it. Output ONLY the corrected function and any imports it needs. No explanation.
"""

FEEDBACK = {
    "nothing": "",
    "boolean": "\nIt did not pass the tests.\n",
    "assertion": "\nThis assertion failed:\n{assertion}\n",
    "traceback": "\nRunning the tests gave:\n{detail}\n",
    "expected": "\nThis assertion failed:\n{assertion}\nIt produced: {actual}\n",
}


def first_failing_assert(code: str, task) -> str:
    """The first assert that does not hold, so `assertion` carries one line, not all three."""
    for a in task.tests:
        if not run(code, [a], task.setup).passed:
            return a
    return task.tests[0]


def actual_value(code: str, assertion: str, task) -> str:
    """What the code returns for the failing assert's call, or why that could not be found.

    Reported rather than guessed: an arm that silently degrades to `assertion` whenever the
    value cannot be recovered is not the arm it claims to be.
    """
    expr = assertion.removeprefix("assert ").split("==")[0].strip()
    probe = f"{code}\n\n{task.setup}\n\nprint(repr({expr}))"
    out = run(probe, [], "")
    if out.status in ("pass", "fail") and out.detail:
        return out.detail.strip().splitlines()[-1][:200]
    return "(could not be evaluated)"


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

    print("  first attempts (cached from project 01)...")
    t0 = time.time()
    sols = solve(tasks, model=args.model, workers=args.workers)
    failed = [s for s in sols if not s.passed]
    print(f"  {len(failed)} first-attempt failures  [{time.time() - t0:.0f}s]\n")

    if not failed:
        print("nothing failed - no repairs to measure")
        return 1

    print("  collecting the failing assertion for each...")
    assertions = [first_failing_assert(s.code, s.task) for s in failed]
    actuals = [actual_value(s.code, a, s.task) for s, a in zip(failed, assertions, strict=True)]

    summary: dict[str, dict] = {}
    fixed_by: dict[str, set[str]] = {}

    for arm, template in FEEDBACK.items():
        t0 = time.time()
        prompts = []
        for s, assertion, actual in zip(failed, assertions, actuals, strict=True):
            fb = template.format(
                assertion=assertion,
                detail=(s.outcome.detail or "the tests failed")[:600],
                actual=actual,
            )
            prompts.append(RETRY.format(prompt=s.task.prompt, code=s.code, feedback=fb))

        raws = generate_many(
            prompts,
            model=args.model,
            temperature=0.0,
            # One seed per arm, or the cache returns the first arm's answer for all five
            # and every arm scores identically for the wrong reason.
            seeds=[list(FEEDBACK).index(arm) + 1] * len(prompts),
            workers=args.workers,
            progress=arm,
        )
        codes = [extract_code(r) if r else "" for r in raws]
        outs = run_many(
            [(c, list(s.task.tests), s.task.setup) for c, s in zip(codes, failed, strict=True)],
            args.workers,
        )
        ok = {s.task.task_id for s, o in zip(failed, outs, strict=True) if o.passed}
        fixed_by[arm] = ok
        chars = sum(len(p) for p in prompts) / len(prompts)
        summary[arm] = {
            "n": len(failed),
            "fixed": len(ok),
            "fix_rate": len(ok) / len(failed),
            "mean_prompt_chars": chars,
        }
        print(
            f"  {arm:10} fixed {len(ok):4}/{len(failed)} ({len(ok) / len(failed):6.1%})  "
            f"prompt {chars:6.0f} chars  [{time.time() - t0:.0f}s]"
        )

    print("\n" + "=" * 76)
    print(f"FEEDBACK CONTENT - {len(failed)} first-attempt failures, {args.model}")
    print("=" * 76)
    for arm in FEEDBACK:
        r = summary[arm]["fix_rate"]
        print(f"  {arm:11} {r:6.1%}  {'#' * round(60 * r)}")

    rates = {k: v["fix_rate"] for k, v in summary.items()}
    best, worst = max(rates, key=rates.get), min(rates, key=rates.get)
    spread = rates[best] - rates[worst]
    baseline = rates["nothing"]

    print(f"\n  best  : {best} at {rates[best]:.1%}")
    print(f"  worst : {worst} at {rates[worst]:.1%}")
    print(f"  spread: {spread:.1%}")
    print(f"\n  richest feedback over no feedback at all : {rates['traceback'] - baseline:+.1%}")
    extra_chars = (
        summary["traceback"]["mean_prompt_chars"] - summary["nothing"]["mean_prompt_chars"]
    )
    print(f"  context it costs to carry the traceback  : {extra_chars:+.0f} chars")

    if spread < 0.05:
        print(
            "\n  Every arm lands within 5 points, including the one that is handed nothing\n"
            "  but 'try again'. On these failures the retry is not reading the error - it is\n"
            "  being asked a second time, and the captured stderr is paying for nothing."
        )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(
                    models=args.model,
                    benchmark="mbpp",
                    n=len(tasks),
                    seeds=list(range(1, len(FEEDBACK) + 1)),
                    extra={"first_attempt_failures": len(failed)},
                ),
                "arms": summary,
                "fixed_by": {k: sorted(v) for k, v in fixed_by.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
