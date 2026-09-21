"""Code to docstring to code. What survives the round trip?

Ask a model to describe a function, then hand that description to a fresh context and ask
it to implement the function. If the description carried everything that mattered, the
result should still pass the original tests.

Where it does not, the description is missing something the code was doing - and the gap
is measurable. This is the documentation question in executable form: `docstring-drift`
found docstrings that describe parameters the function does not have; this asks whether a
docstring describes enough to rebuild the function at all.

The failure is asymmetric and that is the point. A description can be fluent, accurate,
and still omit the boundary condition that three lines of the implementation exist to
handle. Prose has no way to signal that it left something out.

Two arms, so the drop can be attributed:

- `direct`    - implement from MBPP's own task description (the baseline)
- `roundtrip` - implement from the model's description of the reference solution

    python run.py --limit 200
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

DESCRIBE = """Describe exactly what this Python function does, so someone could
reimplement it without seeing the code.

```python
{code}
```

Output ONLY the description as plain prose. No code, no examples, no bullet points.
"""

IMPLEMENT = """Write a Python function named `{entry}` that does exactly this:

{description}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""

DIRECT = """Write a Python function named `{entry}` that does exactly this:

{description}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""


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
    print(f"mbpp: {len(tasks)} tasks, model {args.model}\n")

    print("  describing reference solutions...")
    t0 = time.time()
    raws = generate_many(
        [DESCRIBE.format(code=t.reference) for t in tasks],
        model=args.model,
        temperature=0.0,
        workers=args.workers,
        progress="describe",
    )
    descs = {t.task_id: (r or "").strip() for t, r in zip(tasks, raws, strict=True)}
    print(f"  [{time.time() - t0:.0f}s]")

    arms: dict[str, list[str]] = {"direct": [], "roundtrip": []}
    for arm in arms:
        print(f"  implementing from the {arm} description...")
        tmpl = DIRECT if arm == "direct" else IMPLEMENT
        raws = generate_many(
            [
                tmpl.format(
                    entry=t.entry_point,
                    description=t.prompt if arm == "direct" else descs[t.task_id],
                )
                for t in tasks
            ],
            model=args.model,
            temperature=0.0,
            workers=args.workers,
            progress=arm,
        )
        arms[arm] = [extract_code(r) if r else "" for r in raws]

    passed: dict[str, set[str]] = {}
    for arm, codes in arms.items():
        outs = run_many(
            [(c, list(t.tests), t.setup) for c, t in zip(codes, tasks, strict=True)],
            args.workers,
        )
        passed[arm] = {t.task_id for t, o in zip(tasks, outs, strict=True) if o.passed}

    n = len(tasks)
    d, r = passed["direct"], passed["roundtrip"]
    lost = d - r
    gained = r - d
    lens = [len(descs[t.task_id]) for t in tasks]

    print("\n" + "=" * 68)
    print(f"DOCSTRING ROUNDTRIP - {n} tasks, {args.model}")
    print("=" * 68)
    print(f"  from MBPP's description   : {len(d) / n:6.1%}")
    print(f"  from the model's own prose: {len(r) / n:6.1%}")
    print(f"  drift                     : {(len(r) - len(d)) / n:+.1%}")
    print()
    print(
        f"  solved from code-description but not MBPP's : {len(gained):4} ({len(gained) / n:.1%})"
    )
    print(f"  solved from MBPP's but LOST in the roundtrip: {len(lost):4} ({len(lost) / n:.1%})")
    print(f"\n  mean description length: {sum(lens) / len(lens):.0f} chars")
    print(f"  MBPP's own descriptions average {sum(len(t.prompt) for t in tasks) / n:.0f} chars.")
    if len(r) > len(d):
        print(
            "\n  The model's description of the code beats the benchmark's description of\n"
            "  the task - it was written with the answer in view, which is exactly why a\n"
            "  docstring generated from an implementation is not an independent spec."
        )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(models=args.model, benchmark="mbpp", n=n),
                "direct_pass": len(d) / n,
                "roundtrip_pass": len(r) / n,
                "lost_in_roundtrip": sorted(lost),
                "gained_in_roundtrip": sorted(gained),
                "mean_description_chars": sum(lens) / len(lens),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
