"""The same task, asked five ways. How much of a benchmark score is the prompt format?

`code-eval-harness` measured *output* variance: the same generations score 0% or 94%
depending on how code is extracted from the response. This is the other half - *input*
variance. Same model, same temperature, same tasks, same execution rule. The only thing
that changes is how the task is phrased.

Whatever spread appears here is attributable to formatting alone, and it is a floor on how
much of any published pass@1 is a property of the harness rather than of the model.

Five shapes, all carrying identical information:

- `plain`     - the task description, as MBPP writes it
- `docstring` - the same text inside a function docstring, HumanEval-style
- `comment`   - the same text as a leading `#` comment
- `signature` - the description plus a bare `def` line to complete
- `terse`     - the description with no framing at all

    python run.py --limit 200
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.datasets import load  # noqa: E402
from shared.execute import extract_code, run_many  # noqa: E402
from shared.model import available, generate  # noqa: E402

HERE = Path(__file__).resolve().parent

SHAPES = {
    "plain": (
        "Write a Python function for this task.\n\nTask: {prompt}\n\n"
        "It must satisfy this test:\n{test}\n\n"
        "Output ONLY the function definition and any imports it needs."
    ),
    "docstring": (
        "Complete this Python function.\n\n"
        'def {entry}(...):\n    """{prompt}\n\n    >>> {test_expr}\n    """\n\n'
        "Output ONLY the complete function including its signature."
    ),
    "comment": (
        "# {prompt}\n# Must satisfy: {test}\n\nWrite the Python function. Output ONLY the code."
    ),
    "signature": (
        "Implement `{entry}`.\n\n{prompt}\n\nExample: {test}\n\n"
        "Output ONLY the function definition."
    ),
    "terse": "{prompt}\n{test}",
}


def build(shape: str, task) -> str:
    test = task.tests[0]
    return SHAPES[shape].format(
        prompt=task.prompt,
        test=test,
        entry=task.entry_point,
        test_expr=test.replace("assert ", "").strip(),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1

    tasks = load("mbpp", args.limit)
    print(f"mbpp: {len(tasks)} tasks x {len(SHAPES)} prompt shapes, model {args.model}\n")

    scores: dict[str, float] = {}
    solved: dict[str, set[str]] = {}
    for shape in SHAPES:
        t0 = time.time()
        codes = []
        for i, task in enumerate(tasks, 1):
            raw = generate(build(shape, task), model=args.model, temperature=0.0)
            codes.append(extract_code(raw) if raw else "")
            if i % 100 == 0:
                print(f"    {shape}: {i}/{len(tasks)}", flush=True)
        outs = run_many(
            [(c, list(t.tests), t.setup) for c, t in zip(codes, tasks, strict=True)],
            args.workers,
        )
        ok = {t.task_id for t, o in zip(tasks, outs, strict=True) if o.passed}
        solved[shape] = ok
        scores[shape] = len(ok) / len(tasks)
        print(f"  {shape:10} pass@1 {scores[shape]:6.1%}   [{time.time() - t0:.0f}s]")

    vals = list(scores.values())
    spread = max(vals) - min(vals)
    best = max(scores, key=scores.get)
    worst = min(scores, key=scores.get)

    print("\n" + "=" * 68)
    print(f"PROMPT SHAPE VARIANCE - {len(tasks)} tasks, {args.model}, temperature 0")
    print("=" * 68)
    for shape, v in sorted(scores.items(), key=lambda kv: -kv[1]):
        print(f"  {shape:11} {v:6.1%}  {'#' * round(60 * v)}")
    print()
    print(f"  best  : {best} at {scores[best]:.1%}")
    print(f"  worst : {worst} at {scores[worst]:.1%}")
    print(f"  spread: {spread:.1%} attributable to prompt formatting alone")
    print(f"  stdev : {statistics.pstdev(vals):.1%}")

    # Disagreement is the sharper number: how many tasks flip depending only on phrasing?
    union = set().union(*solved.values())
    inter = set.intersection(*solved.values()) if solved else set()
    flipped = len(union) - len(inter)
    print(f"\n  Solved by at least one shape : {len(union)} ({len(union) / len(tasks):.1%})")
    print(f"  Solved by every shape        : {len(inter)} ({len(inter) / len(tasks):.1%})")
    print(
        f"  Flipped on phrasing alone    : {flipped} ({flipped / len(tasks):.1%}) "
        "<- same model, same task, different wording"
    )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                "model": args.model,
                "n": len(tasks),
                "pass_at_1": scores,
                "spread": spread,
                "solved_by_any": len(union),
                "solved_by_all": len(inter),
                "flipped": flipped,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
