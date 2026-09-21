"""What does irrelevant context cost?

Agents and RAG pipelines both work by putting more in the prompt. A retriever fetches the
top-k whether or not k of them are relevant; an agent carries its scratchpad forward; a
"give the model the whole file" strategy gives it the whole file. The assumption underneath
all of it is that extra context is free, or nearly - worst case the model ignores it.

This measures the worst case. The task is unchanged and fully specified. Everything added
is real Python, and none of it helps: unrelated reference solutions from other MBPP
problems, prepended as if they were retrieved.

    k = 0, 2, 8, 24 unrelated functions

Nothing is removed, no instruction changes, and the task stays last in the prompt - so any
decline is what distraction alone costs.

Two things are reported rather than one. Pass@1 at each k is the headline, but the sharper
number is **how many tasks flip** - solved at k=0 and failed at k=24. An aggregate that
moves two points can hide a lot of individual movement in both directions.

    python run.py --limit 200
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.datasets import load  # noqa: E402
from shared.execute import extract_code, run_many  # noqa: E402
from shared.model import available, generate_many  # noqa: E402
from shared.provenance import stamp  # noqa: E402

HERE = Path(__file__).resolve().parent

KS = [0, 2, 8, 24]

PROMPT = """Write a Python function for this task.
{context}
Task: {prompt}

It must satisfy this test:
{test}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""

CONTEXT_HEADER = """
Here is some code from the repository, for context:

```python
{code}
```
"""


def build_context(pool: list[str], k: int, rnd: random.Random) -> str:
    if k == 0:
        return ""
    picked = rnd.sample(pool, min(k, len(pool)))
    return CONTEXT_HEADER.format(code="\n\n".join(picked))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1

    tasks = load("mbpp", args.limit)
    print(f"mbpp: {len(tasks)} tasks x {len(KS)} context sizes, model {args.model}\n")

    solved: dict[int, set[str]] = {}
    scores: dict[int, float] = {}
    chars: dict[int, float] = {}

    for k in KS:
        t0 = time.time()
        prompts = []
        for i, task in enumerate(tasks):
            # A distractor pool that excludes this task's own reference, so the answer is
            # never accidentally handed over in the context.
            pool = [t.reference for j, t in enumerate(tasks) if j != i]
            rnd = random.Random(args.seed * 100003 + i)
            prompts.append(
                PROMPT.format(
                    context=build_context(pool, k, rnd),
                    prompt=task.prompt,
                    test=task.tests[0],
                )
            )
        chars[k] = sum(len(p) for p in prompts) / len(prompts)

        raws = generate_many(
            prompts,
            model=args.model,
            temperature=0.0,
            workers=args.workers,
            progress=f"k={k}",
        )
        codes = [extract_code(r) if r else "" for r in raws]
        outs = run_many(
            [(c, list(t.tests), t.setup) for c, t in zip(codes, tasks, strict=True)],
            args.workers,
        )
        ok = {t.task_id for t, o in zip(tasks, outs, strict=True) if o.passed}
        solved[k] = ok
        scores[k] = len(ok) / len(tasks)
        print(
            f"  k={k:3}  pass@1 {scores[k]:6.1%}   prompt {chars[k]:7.0f} chars   "
            f"[{time.time() - t0:.0f}s]"
        )

    n = len(tasks)
    lo, hi = KS[0], KS[-1]
    lost = solved[lo] - solved[hi]
    gained = solved[hi] - solved[lo]

    print("\n" + "=" * 72)
    print(f"CONTEXT DILUTION - {n} MBPP tasks, {args.model}")
    print("=" * 72)
    for k in KS:
        print(f"  k={k:3}  {scores[k]:6.1%}  {'#' * round(60 * scores[k])}")

    drop = scores[lo] - scores[hi]
    growth = chars[hi] / chars[lo] if chars[lo] else 0
    print(f"\n  pass@1 change, k=0 -> k={hi}     : {-drop:+.1%}")
    print(f"  prompt grew                    : {growth:.1f}x")
    print(f"\n  solved at k=0, lost by k={hi}    : {len(lost):4} ({len(lost) / n:.1%})")
    print(f"  failed at k=0, gained by k={hi}  : {len(gained):4} ({len(gained) / n:.1%})")
    print(
        f"  churn (either direction)       : {len(lost) + len(gained):4} "
        f"({(len(lost) + len(gained)) / n:.1%})  <- the aggregate hides this"
    )

    if drop > 0:
        print(
            f"\n  {growth:.0f}x the prompt, none of it relevant, costs {drop:.1%} of pass@1.\n"
            "  Extra context is not free, and a retriever that fetches k passages pays this\n"
            "  on every one it gets wrong."
        )
    else:
        print(
            "\n  Irrelevant context did not cost accuracy on this benchmark. MBPP tasks are\n"
            "  short and fully specified, which is the easiest possible case for ignoring\n"
            "  a distractor - this is a floor, not a general result."
        )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(
                    models=args.model,
                    benchmark="mbpp",
                    n=n,
                    seeds=args.seed,
                    extra={"k_values": KS},
                ),
                "pass_at_1": {str(k): scores[k] for k in KS},
                "mean_prompt_chars": {str(k): chars[k] for k in KS},
                "lost": sorted(lost),
                "gained": sorted(gained),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
