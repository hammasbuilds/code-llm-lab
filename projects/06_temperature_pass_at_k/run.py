"""The temperature that maximises pass@1 is not the one that maximises pass@10.

Everyone knows this in the abstract and almost nobody reports the crossover, so people
benchmark at temperature 0 and then deploy an agent that samples ten times, or the reverse.

pass@1 rewards the single most likely answer, so low temperature wins. pass@k only needs
*one* of k samples to be right, so it rewards diversity, and greedy decoding produces none
- at temperature 0 all k samples are identical and pass@10 equals pass@1 exactly.

This sweeps temperature against k and reports where the ordering flips, using the unbiased
pass@k estimator from the Codex paper rather than "did any of my k samples pass", which is
biased upward and depends on how many you happened to draw.

    python run.py --limit 100 --samples 10
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
TEMPS = [0.0, 0.4, 0.7, 1.0]

PROMPT = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k: 1 - C(n-c, k) / C(n, k).

    `n` samples drawn, `c` correct. The naive "any of k passed" is biased upward and
    shifts with n, which makes numbers from different papers incomparable.
    """
    if n - c < k:
        return 1.0
    prod = 1.0
    for i in range(k):
        prod *= (n - c - i) / (n - i)
    return 1.0 - prod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1

    tasks = load("mbpp", args.limit)
    n = args.samples
    ks = [k for k in (1, 2, 5, 10) if k <= n]
    print(f"mbpp: {len(tasks)} tasks x {len(TEMPS)} temperatures x {n} samples\n")

    table: dict[float, dict[int, float]] = {}
    diversity: dict[float, float] = {}

    for temp in TEMPS:
        t0 = time.time()
        correct: list[int] = []
        uniq: list[int] = []
        for i, task in enumerate(tasks, 1):
            codes = []
            for s in range(n):
                # Temperature 0 is deterministic, so drawing n samples is n identical
                # answers - generate once and reuse rather than paying for copies.
                seed = None if temp == 0.0 else s
                if temp == 0.0 and codes:
                    codes.append(codes[0])
                    continue
                raw = generate(
                    PROMPT.format(prompt=task.prompt, test=task.tests[0]),
                    model=args.model,
                    temperature=temp,
                    seed=seed,
                )
                codes.append(extract_code(raw) if raw else "")
            outs = run_many([(c, list(task.tests), task.setup) for c in codes], args.workers)
            correct.append(sum(1 for o in outs if o.passed))
            uniq.append(len(set(codes)))
            if i % 25 == 0 or i == len(tasks):
                print(f"    T={temp}: {i}/{len(tasks)}", flush=True)

        table[temp] = {k: sum(pass_at_k(n, c, k) for c in correct) / len(tasks) for k in ks}
        diversity[temp] = sum(uniq) / len(uniq)
        row = "  ".join(f"@{k} {table[temp][k]:6.1%}" for k in ks)
        print(
            f"  T={temp:<4} {row}   distinct/{n}: {diversity[temp]:.1f}   [{time.time() - t0:.0f}s]"
        )

    print("\n" + "=" * 68)
    print(f"TEMPERATURE vs pass@k - {len(tasks)} tasks, {n} samples, {args.model}")
    print("=" * 68)
    header = "  temp  " + "".join(f"pass@{k}".rjust(10) for k in ks) + "   distinct"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for temp in TEMPS:
        row = f"  {temp:<5} " + "".join(f"{table[temp][k]:9.1%} " for k in ks)
        print(row + f"  {diversity[temp]:8.1f}")

    print()
    for k in ks:
        best = max(TEMPS, key=lambda t: table[t][k])
        print(f"  best temperature for pass@{k:<2}: {best}  ({table[best][k]:.1%})")

    b1, bk = max(TEMPS, key=lambda t: table[t][ks[0]]), max(TEMPS, key=lambda t: table[t][ks[-1]])
    if b1 != bk:
        loss = table[bk][ks[0]] - table[b1][ks[0]]
        gain = table[bk][ks[-1]] - table[b1][ks[-1]]
        print(
            f"\n  The ordering flips: T={b1} wins pass@{ks[0]}, T={bk} wins pass@{ks[-1]}.\n"
            f"  Tuning on pass@{ks[0]} and deploying with k={ks[-1]} costs "
            f"{gain:.1%} of achievable pass@{ks[-1]} (and T={bk} costs {-loss:.1%} at k=1)."
        )
    else:
        print(f"\n  No flip: T={b1} wins at every k measured.")

    (HERE / "results.json").write_text(
        json.dumps(
            {
                "model": args.model,
                "n_tasks": len(tasks),
                "samples": n,
                "pass_at_k": {str(t): {str(k): v for k, v in d.items()} for t, d in table.items()},
                "mean_distinct_samples": diversity,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
