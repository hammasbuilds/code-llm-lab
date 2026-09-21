"""Ask for four functions at once, or four times for one?

MBPP is one function per request, and almost no real work is. A ticket says "add these three
helpers"; an agent editing a file emits several functions in one response. Batching is also
the obvious saving - one prompt, one response, a fraction of the overhead.

So: does the fourth function in a batch get written as well as the first?

Every function is scored against its own original tests either way, so the comparison is
exact. The same tasks, the same model, the same temperature - only the packing changes.

Two numbers, and the second is the one that matters:

- **pass@1 by batch size** - what batching costs overall
- **pass@1 by position within the batch** - whether the cost falls evenly, or lands on
  whatever was asked for last

An overall drop of a few points is easy to accept as the price of efficiency. A drop
concentrated in the last slot is a different fact, because it says the failure depends on
where a request sits in a list rather than on how hard it is.

    python run.py --limit 160
"""

from __future__ import annotations

import argparse
import ast
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

SIZES = [1, 2, 4, 8]

SINGLE = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""

BATCH = """Write {n} separate Python functions, one for each task below.

{body}
Output ONLY the function definitions and any imports they need, one after another in the
same order. No explanation, no tests.
"""


def split_functions(code: str) -> dict[str, str]:
    """Every top-level function in the response, keyed by name, with its imports attached.

    A batch answer is one blob. Scoring it whole would let any one broken function fail the
    other seven, which would measure parsing rather than batching.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}
    lines = code.splitlines()
    header = "\n".join(
        "\n".join(lines[n.lineno - 1 : n.end_lineno])
        for n in tree.body
        if isinstance(n, ast.Import | ast.ImportFrom)
    )
    out: dict[str, str] = {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            body = "\n".join(lines[n.lineno - 1 : n.end_lineno])
            out[n.name] = f"{header}\n\n{body}" if header else body
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=160)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1

    tasks = [t for t in load("mbpp", args.limit) if t.entry_point]
    # Trim to a multiple of the largest batch so every size sees identical tasks.
    tasks = tasks[: len(tasks) // max(SIZES) * max(SIZES)]
    n = len(tasks)
    print(f"mbpp: {n} tasks, batch sizes {SIZES}, model {args.model}\n")

    scores: dict[int, float] = {}
    by_position: dict[int, dict[int, float]] = {}
    missing: dict[int, int] = {}

    for size in SIZES:
        t0 = time.time()
        groups = [tasks[i : i + size] for i in range(0, n, size)]
        prompts = []
        for g in groups:
            if size == 1:
                prompts.append(SINGLE.format(prompt=g[0].prompt, test=g[0].tests[0]))
            else:
                body = "\n".join(
                    f"{i + 1}. Name it `{t.entry_point}`. {t.prompt}\n"
                    f"   It must satisfy: {t.tests[0]}\n"
                    for i, t in enumerate(g)
                )
                prompts.append(BATCH.format(n=size, body=body))

        raws = generate_many(
            prompts,
            model=args.model,
            temperature=0.0,
            workers=args.workers,
            # A batch of 8 needs room for 8 functions.
            num_predict=512 * max(1, size // 2),
            progress=f"batch={size}",
        )

        jobs, owners = [], []
        absent = 0
        for g, raw in zip(groups, raws, strict=True):
            funcs = split_functions(extract_code(raw) if raw else "")
            for pos, task in enumerate(g):
                code = funcs.get(task.entry_point, "")
                if not code:
                    absent += 1
                jobs.append((code, list(task.tests), task.setup))
                owners.append(pos)

        outs = run_many(jobs, args.workers)
        passed = [o.passed for o in outs]
        scores[size] = sum(passed) / len(passed)
        missing[size] = absent
        pos_scores: dict[int, float] = {}
        for pos in range(size):
            hits = [p for p, o in zip(passed, owners, strict=True) if o == pos]
            pos_scores[pos] = sum(hits) / len(hits) if hits else 0.0
        by_position[size] = pos_scores
        print(
            f"  batch={size:2}  pass@1 {scores[size]:6.1%}  "
            f"not emitted {absent:4}  [{time.time() - t0:.0f}s]"
        )

    solo = scores[1]
    biggest = max(SIZES)

    print("\n" + "=" * 76)
    print(f"BATCH vs SINGLE - {n} MBPP tasks, {args.model}")
    print("=" * 76)
    for size in SIZES:
        print(
            f"  batch={size:2}  {scores[size]:6.1%}  {'#' * round(60 * scores[size])}  "
            f"({scores[size] - solo:+.1%})"
        )

    print(f"\n  asking for {biggest} at once costs : {scores[biggest] - solo:+.1%}")
    print(f"  functions never emitted at all : {missing[biggest]} of {n}")

    print(f"\n  pass@1 by position inside a batch of {biggest}:")
    for pos, v in by_position[biggest].items():
        print(f"    slot {pos + 1}: {v:6.1%}  {'#' * round(50 * v)}")

    first, last = by_position[biggest][0], by_position[biggest][biggest - 1]
    print(f"\n  first slot {first:.1%}  vs  last slot {last:.1%}   ({last - first:+.1%})")
    if abs(last - first) > 0.05:
        print(
            "  <- the cost is not spread evenly. Where a request sits in the list changes\n"
            "     whether it gets answered properly, which is not a property of the task."
        )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(models=args.model, benchmark="mbpp", n=n, extra={"sizes": SIZES}),
                "pass_at_1": {str(k): v for k, v in scores.items()},
                "by_position": {
                    str(k): {str(p): s for p, s in v.items()} for k, v in by_position.items()
                },
                "not_emitted": {str(k): v for k, v in missing.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
