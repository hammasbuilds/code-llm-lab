"""Is the code-tuned model actually better at code?

`qwen2.5-coder:14b` and `qwen2.5:14b-instruct` are the same family, the same 14.8B
parameters and the same Q4_K_M quantisation. One of them was trained further on code. That
is as clean as a controlled comparison gets without training anything: the only variable is
the specialisation.

The same pair exists at 3B, so the question can be asked twice - and a specialisation that
helps at one size and not the other is a more useful fact than either measurement alone.

`llama3.2:3b` is included as a different family at 3B, because "coder beats instruct" and
"Qwen beats Llama" are different claims and a single column cannot separate them.

The practical question underneath: a team running one local model for everything has to
decide whether code work justifies a second set of weights in VRAM. That is answered by the
gap, and by which tasks the gap consists of - not by which name sounds more appropriate.

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
from shared.execute import extract_code, run_many  # noqa: E402
from shared.model import available, generate_many  # noqa: E402
from shared.provenance import stamp  # noqa: E402
from shared.solutions import build_prompt  # noqa: E402

HERE = Path(__file__).resolve().parent

# (model, size tier, whether it is the code-specialised one)
FLEET = [
    ("qwen2.5-coder:14b", "14B", True),
    ("qwen2.5:14b-instruct", "14B", False),
    ("qwen2.5-coder:3b", "3B", True),
    ("qwen2.5:3b-instruct", "3B", False),
    ("llama3.2:3b", "3B", False),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--benchmark", default="mbpp", choices=["mbpp", "humaneval"])
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    fleet = [(m, tier, coder) for m, tier, coder in FLEET if available(m)]
    if len(fleet) < 2:
        print("need at least two of the fleet pulled; have:", [m for m, _, _ in fleet])
        return 1
    for m, _, _ in FLEET:
        if not available(m):
            print(f"  skipping {m} - not pulled")

    tasks = load(args.benchmark, args.limit)
    n = len(tasks)
    print(f"\n{args.benchmark}: {n} tasks x {len(fleet)} models\n")

    prompts = [build_prompt(t) for t in tasks]
    solved: dict[str, set[str]] = {}
    scores: dict[str, float] = {}

    for model, tier, coder in fleet:
        t0 = time.time()
        raws = generate_many(
            prompts, model=model, temperature=0.0, workers=args.workers, progress=model
        )
        codes = [extract_code(r) if r else "" for r in raws]
        outs = run_many(
            [(c, list(t.tests), t.setup) for c, t in zip(codes, tasks, strict=True)],
            args.workers,
        )
        ok = {t.task_id for t, o in zip(tasks, outs, strict=True) if o.passed}
        solved[model] = ok
        scores[model] = len(ok) / n
        label = "coder" if coder else "general"
        print(
            f"  {model:24} {tier:>4} {label:8} pass@1 {scores[model]:6.1%}  "
            f"[{time.time() - t0:.0f}s]"
        )

    print("\n" + "=" * 78)
    print(f"CODER vs GENERALIST - {n} {args.benchmark} tasks")
    print("=" * 78)
    for model, tier, coder in fleet:
        tag = "coder  " if coder else "general"
        print(
            f"  {model:24} {tier:>4} {tag} {scores[model]:6.1%}  {'#' * round(50 * scores[model])}"
        )

    pairs = {}
    for tier in ("14B", "3B"):
        c = next((m for m, t, k in fleet if t == tier and k), None)
        g = next((m for m, t, k in fleet if t == tier and not k and m.startswith("qwen")), None)
        if c and g:
            pairs[tier] = (c, g, scores[c] - scores[g])

    if pairs:
        print("\n  same family, same size, same quantisation - only the tuning differs:")
        for tier, (c, g, delta) in pairs.items():
            print(
                f"    {tier}: {c.split(':')[0]}-coder {scores[c]:.1%} vs "
                f"instruct {scores[g]:.1%}   ({delta:+.1%})"
            )

        if len(pairs) == 2 and "14B" in pairs and "3B" in pairs:
            d14, d3 = pairs["14B"][2], pairs["3B"][2]
            print(f"\n  the coder advantage is {d3:+.1%} at 3B and {d14:+.1%} at 14B.")
            if abs(d14) < abs(d3):
                print(
                    "  It shrinks with size - the bigger general model has already learned\n"
                    "  most of what the specialisation buys, so a second set of weights in\n"
                    "  VRAM is hardest to justify exactly where the weights cost most."
                )

        for tier, (c, g, _) in pairs.items():
            only_c = solved[c] - solved[g]
            only_g = solved[g] - solved[c]
            print(
                f"\n  {tier}: {len(only_c)} tasks only the coder solves, "
                f"{len(only_g)} only the generalist does."
            )
            if scores[c] > scores[g] and only_g:
                print(
                    f"     The net gap is {len(only_c) - len(only_g)} tasks, not {len(only_c)} -\n"
                    "     a one-directional reading would overstate it by "
                    f"{len(only_g)}."
                )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(
                    models=[m for m, _, _ in fleet],
                    benchmark=args.benchmark,
                    n=n,
                ),
                "pass_at_1": scores,
                "solved": {m: sorted(s) for m, s in solved.items()},
                "pairs": {
                    t: {"coder": c, "general": g, "delta": d} for t, (c, g, d) in pairs.items()
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
