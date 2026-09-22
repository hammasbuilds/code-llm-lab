"""How much of the repair comes from the error message?

Project 02 showed a self-debug loop is worth two rounds and no more. It varied *how many*
times the model saw the failure. This varies *what it saw* - and that is the part a person
building an agent actually controls.

The decision is concrete. A harness has to choose what to put back in the prompt, and the
options cost different amounts of context:

- `nothing`   - "that was wrong, try again". The cheapest possible signal.
- `boolean`   - the tests failed, no detail.
- `assertion` - the assert that failed and nothing else.
- `traceback` - the full traceback: exception, source line, and the caret under the call.
- `expected`  - the failing assert plus what the code produced instead.
- `padding`   - a control. Matched to `expected`'s length, character for character, with
                true statements about the harness that say nothing about the failure.

The arms **replace** each other; they are not nested. `expected` is the only one that
strictly contains another (`assertion`), and `traceback` contains the same source line
wrapped in ceremony. That is the comparison worth having: the same fact, presented two
ways, at two prices.

`padding` is here because every informative arm is also a longer arm. Without it, "the
richer arm did better" and "the longer arm did better" are the same observation, and an
earlier version of this project attributed a difference to length without ever testing it.

Every arm starts from the **same** failed first attempt, so the only variable is the
feedback. One retry each, because project 02 established that later rounds add nothing.

    python run.py --limit 972
"""

from __future__ import annotations

import argparse
import json
import math
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
    # A control, not a strategy anyone would use. Every informative arm is also a *longer*
    # arm, so a difference between them could be the content or could be the extra tokens.
    # This one is padded to exactly the length of `expected` with true statements about the
    # harness that say nothing whatsoever about this failure. Whatever it scores is what
    # length alone buys.
    "padding": "{padding}",
}

# Repeated and cut to length. Every sentence is true and none of it is about the task,
# the code, or why it failed.
FILLER = (
    "The tests are run in a separate process. "
    "The process has a wall-clock limit. "
    "Standard output and standard error are both captured. "
    "The working directory is a temporary one. "
)


def mcnemar(a: set[str], b: set[str]) -> tuple[int, int, float]:
    """(fixed by a only, fixed by b only, exact two-sided p) over the discordant tasks.

    Exact binomial rather than the chi-square approximation, because several of these
    comparisons have single-digit discordant counts and the approximation is not usable
    there - which is exactly where a difference is most likely to be over-read.
    """
    only_a, only_b = len(a - b), len(b - a)
    n = only_a + only_b
    if n == 0:
        return 0, 0, 1.0
    k = min(only_a, only_b)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2**n * 2
    return only_a, only_b, min(1.0, p)


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

    The probe *prints* the value, so the answer is on stdout and the probe succeeds. An
    earlier version read `out.detail` instead, which a successful Outcome leaves empty -
    so it returned "(could not be evaluated)" precisely when the value was available, and
    the `expected` arm carried that literal string for every task in two published runs.
    The tell was in the results file: `expected` minus `assertion` was 38.0000 characters,
    a constant, and real values do not all have the same length.
    """
    expr = assertion.removeprefix("assert ").split("==")[0].strip()
    probe = f"{code}\n\n{task.setup}\n\nprint(repr({expr}))"
    out = run(probe, [], "")
    if out.stdout:
        return out.stdout.strip().splitlines()[-1][:200]
    # A genuine failure to evaluate: the call raises, loops, or the expression could not be
    # recovered from the assert. Naming it is right; returning it for a success was not.
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

    # `expected`'s length per task, so `padding` can be matched to it exactly rather than
    # on the mean - the mean would leave individual prompts mismatched in both directions.
    expected_len = [
        len(FEEDBACK["expected"].format(assertion=a, actual=v, detail="", padding=""))
        for a, v in zip(assertions, actuals, strict=True)
    ]
    paddings = [(FILLER * (n // len(FILLER) + 1))[:n] for n in expected_len]

    summary: dict[str, dict] = {}
    fixed_by: dict[str, set[str]] = {}

    for arm, template in FEEDBACK.items():
        t0 = time.time()
        prompts = []
        for s, assertion, actual, padding in zip(
            failed, assertions, actuals, paddings, strict=True
        ):
            fb = template.format(
                assertion=assertion,
                # The real traceback, not `detail`. `detail` is the last line of stderr,
                # which for an AssertionError is the bare word "AssertionError" - fourteen
                # characters carrying no file, no line and no values. Two earlier runs of
                # this project sent that string and reported the result as a finding about
                # tracebacks.
                detail=(s.outcome.traceback or "the tests failed")[:600],
                actual=actual,
                padding=padding,
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

    print(f"\n  best  : {best} at {rates[best]:.1%}")
    print(f"  worst : {worst} at {rates[worst]:.1%}")
    print(f"  spread: {spread:.1%}")

    # Every arm retries the same failures, so the arms are paired and the unpaired
    # difference in rates throws away which tasks moved. An earlier write-up of this
    # project called a 1-task gap a finding; these are the numbers that would have
    # refused it.
    print("\n  --- paired, vs `nothing` (exact McNemar on discordant tasks) ---")
    comparisons = {}
    for arm in FEEDBACK:
        if arm == "nothing":
            continue
        b, c, p = mcnemar(fixed_by[arm], fixed_by["nothing"])
        comparisons[f"{arm}_vs_nothing"] = {"only_arm": b, "only_other": c, "p": p}
        flag = "  <- significant" if p < 0.05 else ""
        print(f"    {arm:11} +{b:>3} / -{c:<3}  p = {p:.4f}{flag}")

    # The two that matter for "is it the content or the length", stated as comparisons
    # rather than left for a reader to subtract.
    print("\n  --- paired, the two controls ---")
    for a, b_arm, why in (
        ("padding", "nothing", "does length alone buy anything?"),
        ("expected", "assertion", "does adding the actual value help or cost?"),
        ("traceback", "assertion", "does the assert wrapped in a traceback help or cost?"),
    ):
        b, c, p = mcnemar(fixed_by[a], fixed_by[b_arm])
        comparisons[f"{a}_vs_{b_arm}"] = {"only_arm": b, "only_other": c, "p": p}
        print(f"    {a:10} vs {b_arm:10} +{b:>3} / -{c:<3}  p = {p:.4f}   {why}")

    union = set().union(*fixed_by.values())
    print(
        f"\n  ceiling: {len(union)}/{len(failed)} ({len(union) / len(failed):.1%}) of failures "
        f"were fixed by at least one\n  of the {len(FEEDBACK)} framings. The rest are not a "
        "communication problem."
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
                "comparisons": comparisons,
                "fixed_any": sorted(union),
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
