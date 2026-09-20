"""Where does a 5x bigger coder model actually pay?

qwen2.5-coder ships at 3B and 14B - same family, same training recipe, same tokenizer.
That makes the size comparison clean in a way that comparing across families never is.

The aggregate answer ("the 14B scores higher") is not interesting. The useful question is
*where* the extra 7.6 GB of weights goes: is the gain spread evenly, or concentrated in a
subset of problems the small model simply cannot do? If it is concentrated, then for the
other problems the 3B is the correct engineering choice and the benchmark average hides it.

So every task is put in one of four buckets:

- `both`    - both sizes solve it. The 14B bought nothing here.
- `big`     - only the 14B. This is what the size is for.
- `small`   - only the 3B. Noise, or a prompt the big model overthinks.
- `neither` - neither. The size did not matter because nothing was enough.

    python run.py --benchmark mbpp --limit 200
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
from shared.model import available, generate  # noqa: E402

HERE = Path(__file__).resolve().parent
SIZES = ["qwen2.5-coder:3b", "qwen2.5-coder:14b"]

MBPP_PROMPT = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""

HUMANEVAL_PROMPT = """Complete this Python function.

{prompt}

Output ONLY the complete function including its signature. No explanation, no tests.
"""


def build_prompt(task) -> str:
    if task.is_mbpp:
        return MBPP_PROMPT.format(prompt=task.prompt, test=task.tests[0])
    return HUMANEVAL_PROMPT.format(prompt=task.prompt)


def solve_all(tasks, model: str) -> dict[str, str]:
    out: dict[str, str] = {}
    t0 = time.time()
    for i, task in enumerate(tasks, 1):
        raw = generate(build_prompt(task), model=model, temperature=0.0)
        out[task.task_id] = extract_code(raw) if raw else ""
        if i % 50 == 0 or i == len(tasks):
            rate = (time.time() - t0) / i
            print(
                f"    {i}/{len(tasks)}  {rate:.1f}s each  "
                f"eta {rate * (len(tasks) - i) / 60:.0f} min",
                flush=True,
            )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default="mbpp", choices=["mbpp", "humaneval"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    for m in SIZES:
        if not available(m):
            print(f"{m} not available")
            return 1

    tasks = load(args.benchmark, args.limit)
    print(f"{args.benchmark}: {len(tasks)} tasks")

    passed: dict[str, set[str]] = {}
    for model in SIZES:
        print(f"\n  generating with {model}")
        sols = solve_all(tasks, model)
        outcomes = run_many(
            [(sols[t.task_id], list(t.tests), t.setup) for t in tasks], args.workers
        )
        ok = {t.task_id for t, o in zip(tasks, outcomes, strict=True) if o.passed}
        passed[model] = ok
        print(f"    pass@1: {len(ok)}/{len(tasks)}  ({len(ok) / len(tasks):.1%})")

    small, big = passed[SIZES[0]], passed[SIZES[1]]
    ids = {t.task_id for t in tasks}
    buckets = {
        "both": small & big,
        "big_only": big - small,
        "small_only": small - big,
        "neither": ids - small - big,
    }

    n = len(tasks)
    print("\n" + "=" * 68)
    print(f"WHERE THE SIZE GOES - {args.benchmark}, {n} tasks")
    print("=" * 68)
    print(f"  3B  pass@1 : {len(small) / n:.1%}")
    print(f"  14B pass@1 : {len(big) / n:.1%}")
    print(f"  difference : {(len(big) - len(small)) / n:+.1%}")
    print()
    for name, s in buckets.items():
        bar = "#" * round(40 * len(s) / n)
        print(f"  {name:11} {len(s):4}  {len(s) / n:6.1%}  {bar}")

    solved_by_either = len(small | big)
    if solved_by_either:
        print(
            f"\n  Of the {solved_by_either} tasks either size can solve, the 3B already "
            f"handles {len(small) / solved_by_either:.1%}."
        )
    if len(big) > len(small):
        print(
            f"  The 14B's entire advantage is {len(buckets['big_only'])} tasks "
            f"({len(buckets['big_only']) / n:.1%} of the benchmark)."
        )
    if buckets["small_only"]:
        print(
            f"  It also loses {len(buckets['small_only'])} tasks the 3B gets right, "
            "which bounds how much of the gap is real rather than noise."
        )

    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / f"results_{args.benchmark}.json").write_text(
        json.dumps(
            {
                "benchmark": args.benchmark,
                "n": n,
                "pass_at_1": {m: len(passed[m]) / n for m in SIZES},
                "buckets": {k: sorted(v) for k, v in buckets.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / f'results_{args.benchmark}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
