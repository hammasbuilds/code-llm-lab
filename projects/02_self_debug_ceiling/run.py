"""How many rounds of test feedback are worth paying for?

Give a model its failing test output and let it try again. Everyone does this. The
question nobody answers with a number is when to stop: round 2, round 5, round 20?

This runs rounds 1 through N and reports the marginal gain of each. The interesting
outcome is the shape of the curve, and specifically whether it flattens - because if
rounds 3-5 add almost nothing, then every agent looping five times is paying five times
the tokens for the value of two.

**The oracle here is real.** Unlike a revision loop judged by another model, a failing
assert is ground truth: the code either passes or it does not. So "did the extra round
help" is a fact rather than an opinion.

One thing the curve cannot show: a fix that passes the tests but is wrong. Feedback-driven
repair optimises for the tests it is shown, which is exactly what makes a thin test suite
dangerous - see the mbpp-false-accepts repo for how thin three asserts are.

    python run.py --rounds 5 --limit 150
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

HERE = Path(__file__).resolve().parent

FIRST = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""

RETRY = """This Python function is wrong.

Task: {prompt}

Your code:
```python
{code}
```

Running the tests gave:
{error}

Fix it. Output ONLY the corrected function and any imports it needs. No explanation.
"""


def first_prompt(task) -> str:
    if task.is_mbpp:
        return FIRST.format(prompt=task.prompt, test=task.tests[0])
    return f"Complete this Python function.\n\n{task.prompt}\n\nOutput ONLY the complete function."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default="mbpp", choices=["mbpp", "humaneval"])
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1

    tasks = load(args.benchmark, args.limit)
    print(f"{args.benchmark}: {len(tasks)} tasks, up to {args.rounds} rounds\n")

    # solved_at[task_id] = the round that first passed, or None
    solved_at: dict[str, int | None] = {}
    state: dict[str, tuple[str, str]] = {}  # task_id -> (code, last error)
    per_round: list[int] = []
    t0 = time.time()

    for rnd in range(1, args.rounds + 1):
        todo = [t for t in tasks if solved_at.get(t.task_id) is None]
        if not todo:
            print(f"  round {rnd}: nothing left to fix")
            per_round.append(0)
            continue

        prompts = []
        for task in todo:
            if rnd == 1:
                prompts.append(first_prompt(task))
            else:
                code, err = state[task.task_id]
                prompts.append(
                    RETRY.format(
                        prompt=task.prompt if task.is_mbpp else task.prompt[:600],
                        code=code,
                        error=err or "the tests failed",
                    )
                )
        # Seeded per round so a retry is a genuinely new attempt rather than the same
        # greedy decode returning the same wrong answer.
        raws = generate_many(
            prompts,
            model=args.model,
            temperature=0.0,
            seeds=[rnd] * len(prompts),
            workers=args.workers,
            progress=f"round {rnd}",
        )
        codes = [extract_code(r) if r else "" for r in raws]
        outcomes = run_many(
            [(c, list(t.tests), t.setup) for c, t in zip(codes, todo, strict=True)],
            args.workers,
        )
        newly = 0
        for task, code, outcome in zip(todo, codes, outcomes, strict=True):
            state[task.task_id] = (code, outcome.detail)
            if outcome.passed:
                solved_at[task.task_id] = rnd
                newly += 1

        per_round.append(newly)
        cum = sum(per_round)
        print(
            f"  round {rnd}: +{newly} newly solved, cumulative "
            f"{cum}/{len(tasks)} ({cum / len(tasks):.1%})  "
            f"[{time.time() - t0:.0f}s]"
        )

    n = len(tasks)
    total = sum(per_round)
    print("\n" + "=" * 68)
    print(f"SELF-DEBUG CEILING - {args.benchmark}, {n} tasks, {args.model}")
    print("=" * 68)
    print(f"  {'round':>6} {'newly solved':>13} {'cumulative':>11} {'share of total gain':>21}")
    cum = 0
    for i, newly in enumerate(per_round, 1):
        cum += newly
        share = newly / total if total else 0
        print(f"  {i:6} {newly:13} {cum / n:10.1%} {share:20.1%}  {'#' * round(30 * share)}")

    if total:
        first_two = sum(per_round[:2]) / total
        print(f"\n  Rounds 1-2 captured {first_two:.1%} of everything the loop ever achieved.")
        rest = sum(per_round[2:])
        print(
            f"  Rounds 3-{args.rounds} added {rest} tasks "
            f"({rest / n:.1%} of the benchmark) for "
            f"{(args.rounds - 2) / args.rounds:.0%} of the compute."
        )

    (HERE / f"results_{args.benchmark}.json").write_text(
        json.dumps(
            {
                **stamp(
                    models=args.model,
                    benchmark=args.benchmark,
                    n=n,
                    seeds=list(range(1, args.rounds + 1)),  # one per round, see above
                    extra={"rounds": args.rounds},
                ),
                "per_round_newly_solved": per_round,
                "cumulative_pass": [sum(per_round[: i + 1]) / n for i in range(len(per_round))],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / f'results_{args.benchmark}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
