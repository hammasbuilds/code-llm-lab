"""Temperature 0 is not the same as deterministic.

Everything in this repo that does not vary temperature runs at 0, on the usual
understanding that greedy decoding makes a run reproducible. Published evaluations lean on
the same assumption - a pass@1 at temperature 0 is reported as a fact about the model, not
as one draw.

It is not quite true. Greedy decoding picks the highest-probability token, but the
probabilities come out of floating-point arithmetic whose order is not fixed: batching,
kernel selection and GPU reduction order all move the last bits. Where two tokens are close,
that is enough to change which one wins, and the rest of the sequence follows.

This measures it on the one thing that matters - whether the *answer changes*, not whether
the bytes do:

- how often N runs of the identical prompt produce different text
- how often they produce a different pass/fail verdict
- the spread between the best and worst run's pass@1

The last number is the one to carry away. If two runs of the same evaluation differ by more
than a point, then a paper reporting 74% and another reporting 76% may be reporting the same
model, and the cache in this repo is not just a speed-up - it is what makes every other
project here reproducible at all.

The generation cache is bypassed for this project, or every run after the first would be
a copy by construction.

    python run.py --limit 120 --runs 5
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.datasets import load  # noqa: E402
from shared.execute import extract_code, run_many  # noqa: E402
from shared.model import available, generate  # noqa: E402
from shared.provenance import stamp  # noqa: E402
from shared.solutions import build_prompt  # noqa: E402

HERE = Path(__file__).resolve().parent


class RunFailed(RuntimeError):
    """A run lost too many generations to be a measurement of anything."""


def generate_uncached(
    prompts: list[str], model: str, workers: int, label: str, tolerate: float = 0.02
) -> list[str]:
    """Same as generate_many, with the cache off. The cache is the thing under test.

    A dead request is not a wrong answer. `generate` returns None when ollama cannot be
    reached in time, and turning that into "" hands the scorer an empty program, which
    fails its tests and is indistinguishable from a model that got the question wrong.

    That is not hypothetical. Three of eight runs here overlapped another session loading a
    second 14B model onto the same card; requests began timing out, and those runs scored
    48.8%, 69.8% and 45.2% against a 76.0-76.2% cluster from the five clean ones. Reported
    as-is it read as "31.8% of tasks flip verdict at temperature 0" - a spectacular finding,
    and entirely an artefact of HTTP timeouts.

    So a run that loses more than `tolerate` of its generations raises instead of returning
    a plausible-looking list of empty strings.
    """
    out: list[str] = [""] * len(prompts)
    done = 0
    lost = 0

    def one(i: int) -> None:
        nonlocal done, lost
        text = generate(prompts[i], model=model, temperature=0.0, use_cache=False)
        if text is None:
            lost += 1
        out[i] = text or ""
        done += 1
        if done % 50 == 0:
            print(f"    {label}: {done}/{len(prompts)}  lost {lost}", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, range(len(prompts))))

    if lost > tolerate * len(prompts):
        raise RunFailed(
            f"{label}: {lost} of {len(prompts)} generations never returned "
            f"({lost / len(prompts):.1%}). Scoring these as failures would report a "
            "model that is fine as a model that flips. Check ollama is not sharing the "
            "card with another model."
        )
    if lost:
        print(f"    {label}: WARNING {lost} generations lost", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=120)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1

    tasks = load("mbpp", args.limit)
    n = len(tasks)
    prompts = [build_prompt(t) for t in tasks]
    print(f"mbpp: {n} tasks x {args.runs} identical runs at temperature 0, {args.model}\n")

    texts: list[list[str]] = []
    verdicts: list[list[bool]] = []
    per_run: list[float] = []

    for r in range(args.runs):
        t0 = time.time()
        raws = generate_uncached(prompts, args.model, args.workers, f"run {r + 1}")
        codes = [extract_code(x) if x else "" for x in raws]
        outs = run_many(
            [(c, list(t.tests), t.setup) for c, t in zip(codes, tasks, strict=True)],
            args.workers,
        )
        ok = [o.passed for o in outs]
        texts.append([x.strip() for x in raws])
        verdicts.append(ok)
        per_run.append(sum(ok) / n)
        print(f"  run {r + 1}: pass@1 {per_run[-1]:6.1%}   [{time.time() - t0:.0f}s]")

    text_varied = sum(len({texts[r][i] for r in range(args.runs)}) > 1 for i in range(n))
    verdict_varied = sum(len({verdicts[r][i] for r in range(args.runs)}) > 1 for i in range(n))
    distinct = [len({texts[r][i] for r in range(args.runs)}) for i in range(n)]

    lo, hi = min(per_run), max(per_run)

    print("\n" + "=" * 76)
    print(f"DETERMINISM AT T=0 - {n} tasks x {args.runs} runs, {args.model}")
    print("=" * 76)
    print(
        f"  identical prompt gave different TEXT    : {text_varied:4}/{n} ({text_varied / n:.1%})"
    )
    print(
        f"  identical prompt gave a different VERDICT: {verdict_varied:4}/{n} "
        f"({verdict_varied / n:.1%})"
    )
    print(
        f"  mean distinct outputs per task          : {statistics.mean(distinct):.2f}"
        f" of {args.runs}"
    )
    print(f"\n  pass@1 across runs : {lo:.1%} - {hi:.1%}   (spread {hi - lo:.1%})")
    print(f"  mean               : {statistics.mean(per_run):.1%}")
    if len(per_run) > 1:
        print(f"  stdev              : {statistics.pstdev(per_run):.2%}")

    print("\n  distinct outputs per task:")
    for k, c in sorted(Counter(distinct).items()):
        print(f"    {k} distinct: {c:4} tasks  {'#' * round(50 * c / n)}")

    if verdict_varied:
        print(
            f"\n  {verdict_varied} tasks ({verdict_varied / n:.1%}) flip between pass and fail\n"
            "  with nothing changed at all - same prompt, same model, temperature 0. A single\n"
            "  run of an evaluation is one draw from this, not a measurement of the model."
        )
    else:
        print(
            "\n  Every task held its verdict across all runs. Decoding was effectively\n"
            "  deterministic here - which is the result, and it is worth having stated\n"
            "  rather than assumed."
        )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(
                    models=args.model,
                    benchmark="mbpp",
                    n=n,
                    samples=args.runs,
                    extra={"cache": "bypassed"},
                ),
                "pass_at_1_per_run": per_run,
                "spread": hi - lo,
                "tasks_with_varying_text": text_varied,
                "tasks_with_varying_verdict": verdict_varied,
                "mean_distinct_outputs": statistics.mean(distinct),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
