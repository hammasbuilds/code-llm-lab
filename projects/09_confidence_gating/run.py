"""Can you auto-merge on the model's own confidence?

The practical shape of this question: a pipeline generates a patch, and something has to
decide whether it ships without a human. Asking the model how sure it is costs one extra
line of prompt, so it is the first thing anyone tries.

For that to work, confidence has to *discriminate* - the score on solutions that pass has
to separate from the score on solutions that fail. A model that answers 90 to everything is
perfectly calibrated on average and completely useless as a gate, and an average calibration
error cannot tell the two apart.

So this reports separation and the gate directly, not a calibration curve:

- mean confidence on passing vs failing solutions, and the gap between them
- for each threshold, what you would actually get: **precision** (of what you auto-merged,
  how much was correct) and **coverage** (how much you auto-merged at all)

A gate is only worth having if some threshold beats shipping everything unchecked.

    python run.py --limit 250
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.datasets import load  # noqa: E402
from shared.execute import extract_code, run_many  # noqa: E402
from shared.model import available, generate_many  # noqa: E402
from shared.provenance import stamp  # noqa: E402

HERE = Path(__file__).resolve().parent

PROMPT = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

Output the function, then on the LAST line state how confident you are that your code is
correct, as an integer from 0 to 100, in exactly this form:

CONFIDENCE: <number>
"""

_CONF = re.compile(r"CONFIDENCE\s*:\s*(\d{1,3})")

THRESHOLDS = [0, 50, 60, 70, 80, 90, 95, 100]


def parse_confidence(raw: str | None) -> int | None:
    """The last CONFIDENCE line, clamped to 0-100, or None if it never gave one.

    The *last* match on purpose: the prompt asks for it on the final line, and a model that
    restates the instruction before answering would otherwise have its own echo parsed as
    the answer.
    """
    if not raw:
        return None
    m = _CONF.findall(raw)
    if not m:
        return None
    return max(0, min(100, int(m[-1])))


def gate(rows: list[tuple[int, bool]], threshold: int) -> tuple[float, float, int]:
    """(precision, coverage, n_merged) for auto-merging everything at or above `threshold`."""
    merged = [ok for conf, ok in rows if conf >= threshold]
    if not merged:
        return 0.0, 0.0, 0
    return sum(merged) / len(merged), len(merged) / len(rows), len(merged)


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

    t0 = time.time()
    raws = generate_many(
        [PROMPT.format(prompt=t.prompt, test=t.tests[0]) for t in tasks],
        model=args.model,
        temperature=0.0,
        workers=args.workers,
        progress="solve+confidence",
    )
    codes = [extract_code(r) if r else "" for r in raws]
    confs = [parse_confidence(r) for r in raws]
    outs = run_many(
        [(c, list(t.tests), t.setup) for c, t in zip(codes, tasks, strict=True)],
        args.workers,
    )
    print(f"  [{time.time() - t0:.0f}s]")

    rows = [(c, o.passed) for c, o in zip(confs, outs, strict=True) if c is not None]
    stated = len(rows)
    n = len(tasks)
    overall = sum(o.passed for o in outs) / n

    print("\n" + "=" * 72)
    print(f"CONFIDENCE GATING - {n} MBPP tasks, {args.model}")
    print("=" * 72)
    print(f"  stated a confidence      : {stated}/{n} ({stated / n:.1%})")
    print(f"  pass@1, all tasks        : {overall:.1%}")

    if not rows:
        print("\n  no parseable confidences - nothing to gate on")
        return 1

    # The baseline a gate has to beat is the pass rate of the population it can act on -
    # the tasks that stated a confidence - not the pass rate over all tasks. Those differ
    # whenever failing to answer in the required form correlates with failing the task,
    # and comparing against the wrong one would credit the gate for that correlation.
    base = sum(ok for _, ok in rows) / len(rows)
    if abs(base - overall) > 1e-9:
        print(f"  pass@1, those tasks only : {base:.1%}  <- the baseline a gate must beat")

    yes = [c for c, ok in rows if ok]
    no = [c for c, ok in rows if not ok]
    mean_yes = statistics.mean(yes) if yes else 0.0
    mean_no = statistics.mean(no) if no else 0.0

    print(f"\n  mean confidence when correct : {mean_yes:6.1f}   (n={len(yes)})")
    print(f"  mean confidence when wrong   : {mean_no:6.1f}   (n={len(no)})")
    print(f"  separation                   : {mean_yes - mean_no:+6.1f} points")

    distinct = sorted({c for c, _ in rows})
    print(f"\n  distinct confidence values used: {len(distinct)}  {distinct[:12]}")

    header = f"{'threshold':>9} {'merged':>7} {'coverage':>9} {'precision':>10} {'vs base':>9}"
    print("\n  " + header)
    table = {}
    for th in THRESHOLDS:
        prec, cov, merged = gate(rows, th)
        table[th] = {"precision": prec, "coverage": cov, "merged": merged}
        delta = f"{prec - base:+.1%}" if merged else "-"
        print(f"  {th:9} {merged:7} {cov:9.1%} {prec:10.1%} {delta:>11}")

    useful = [th for th in THRESHOLDS if table[th]["merged"] and table[th]["precision"] > base]
    if useful:
        best = max(useful, key=lambda t: table[t]["precision"])
        print(
            f"\n  Gating at {best} lifts precision to {table[best]['precision']:.1%} "
            f"(+{table[best]['precision'] - base:.1%}) while auto-merging "
            f"{table[best]['coverage']:.1%} of tasks."
        )
    else:
        print(
            "\n  No threshold beats shipping everything unchecked. The confidence the model\n"
            "  states does not separate its correct answers from its wrong ones, so there is\n"
            "  nothing here to gate on."
        )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(models=args.model, benchmark="mbpp", n=n),
                "stated_confidence": stated,
                "pass_at_1_all_tasks": overall,
                "pass_at_1_gatable": base,
                "mean_confidence_correct": mean_yes,
                "mean_confidence_wrong": mean_no,
                "separation": mean_yes - mean_no,
                "distinct_values": distinct,
                "gate": {str(k): v for k, v in table.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
