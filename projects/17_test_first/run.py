"""Does writing the tests first help the model write the code?

Test-driven development is advice about people: writing the test first forces you to decide
what the function does before deciding how. Whether that transfers to a model is an
empirical question, and it is the kind of thing a team will adopt on the strength of the
analogy alone.

Four arms, from cheapest to most elaborate:

- `direct`     - just write the function
- `plan`       - describe the approach first, then write it (the generic "think first" arm)
- `tests_then` - write tests first, then the implementation, in one response
- `tests_seen` - write tests, then implement in a **fresh** context given only those tests

`plan` is the control that makes the result mean something. If `tests_then` beats `direct`
by the same margin `plan` does, then nothing about *tests* helped - the model just produced
more tokens before answering, and any preamble would have done.

`tests_seen` separates the two mechanisms that get conflated: does writing tests help
because the act of writing them clarifies the task, or because the tests are then in the
context? Only the second survives a context reset.

Scored against MBPP's own tests throughout. The model's tests are never the oracle - it
would be marking its own homework.

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
from shared.execute import extract_solution, run_many, strip_self_tests  # noqa: E402
from shared.model import available, generate_many  # noqa: E402
from shared.provenance import stamp  # noqa: E402

HERE = Path(__file__).resolve().parent

DIRECT = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""

PLAN = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

First describe your approach in two or three sentences. Then write the function.

End your response with the function definition and any imports it needs.
"""

TESTS_THEN = """You are writing a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

First write assert statements covering the behaviour, including edge cases.
Then write the function that satisfies them.

End your response with the function definition and any imports it needs.
"""

WRITE_TESTS = """Write assert statements that test a Python function for this task.

Task: {prompt}

One example: {test}

Output ONLY assert statements, one per line. No code, no explanation.
"""

FROM_TESTS = """Write a Python function that satisfies these tests.

Task: {prompt}

Tests:
{tests}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1

    tasks = load("mbpp", args.limit)
    n = len(tasks)
    print(f"mbpp: {n} tasks x 4 arms, model {args.model}\n")

    def submission(raw: str) -> str:
        """What actually gets run: the last defining block, with the model's own asserts
        removed. Leaving them in submits the model's tests alongside its answer, and they
        execute above the `def` - so a correct function fails with NameError, and a wrong
        self-test rejects a right answer. Either way the model marks its own homework."""
        return strip_self_tests(extract_solution(raw)) if raw else ""

    def score(codes: list[str]) -> tuple[set[str], float]:
        outs = run_many(
            [(c, list(t.tests), t.setup) for c, t in zip(codes, tasks, strict=True)],
            args.workers,
        )
        ok = {t.task_id for t, o in zip(tasks, outs, strict=True) if o.passed}
        return ok, len(ok) / n

    solved: dict[str, set[str]] = {}
    scores: dict[str, float] = {}
    lengths: dict[str, float] = {}

    for arm, template in (("direct", DIRECT), ("plan", PLAN), ("tests_then", TESTS_THEN)):
        t0 = time.time()
        raws = generate_many(
            [template.format(prompt=t.prompt, test=t.tests[0]) for t in tasks],
            model=args.model,
            temperature=0.0,
            workers=args.workers,
            num_predict=768 if arm != "direct" else 512,
            progress=arm,
        )
        lengths[arm] = sum(len(r or "") for r in raws) / n
        # extract_solution, not extract_code: `tests_then` asks for asserts before the
        # function, so the first fenced block is the tests. Scoring that instead of the
        # answer put this arm at 17.0% against 77.0% for answering directly.
        solved[arm], scores[arm] = score([submission(r) for r in raws])
        print(f"  {arm:11} pass@1 {scores[arm]:6.1%}   [{time.time() - t0:.0f}s]")

    # tests_seen: two hops, with nothing carried across but the tests themselves.
    t0 = time.time()
    test_raws = generate_many(
        [WRITE_TESTS.format(prompt=t.prompt, test=t.tests[0]) for t in tasks],
        model=args.model,
        temperature=0.0,
        workers=args.workers,
        num_predict=384,
        progress="write tests",
    )
    written = [(r or "").strip() or t.tests[0] for r, t in zip(test_raws, tasks, strict=True)]
    raws = generate_many(
        [FROM_TESTS.format(prompt=t.prompt, tests=w) for t, w in zip(tasks, written, strict=True)],
        model=args.model,
        temperature=0.0,
        workers=args.workers,
        progress="implement",
    )
    lengths["tests_seen"] = sum(len(r or "") for r in raws) / n
    solved["tests_seen"], scores["tests_seen"] = score([submission(r) for r in raws])
    print(f"  {'tests_seen':11} pass@1 {scores['tests_seen']:6.1%}   [{time.time() - t0:.0f}s]")

    base = scores["direct"]
    print("\n" + "=" * 76)
    print(f"TEST FIRST - {n} MBPP tasks, {args.model}")
    print("=" * 76)
    for arm in ("direct", "plan", "tests_then", "tests_seen"):
        print(
            f"  {arm:12} {scores[arm]:6.1%}  {'#' * round(55 * scores[arm])}  "
            f"({scores[arm] - base:+.1%})"
        )

    tdd = scores["tests_then"] - base
    thinking = scores["plan"] - base
    print(f"\n  writing tests first is worth : {tdd:+.1%}")
    print(f"  any preamble at all is worth : {thinking:+.1%}")
    print(f"  attributable to *tests*      : {tdd - thinking:+.1%}")

    if abs(tdd - thinking) < 0.02:
        print(
            "\n  Writing tests first and simply thinking out loud first land within two\n"
            "  points of each other. On this benchmark the gain is from producing tokens\n"
            "  before answering, not from the tests - the TDD framing is doing no work."
        )

    print(
        f"\n  carried into a fresh context : {scores['tests_seen'] - base:+.1%}  "
        f"({scores['tests_seen'] - scores['tests_then']:+.1%} vs same-context)"
    )
    print(
        "\n  mean response length: "
        + "  ".join(f"{a}={lengths[a]:.0f}" for a in ("direct", "plan", "tests_then", "tests_seen"))
    )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(models=args.model, benchmark="mbpp", n=n),
                "pass_at_1": scores,
                "mean_response_chars": lengths,
                "tdd_over_direct": tdd,
                "plan_over_direct": thinking,
                "attributable_to_tests": tdd - thinking,
                "solved": {k: sorted(v) for k, v in solved.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
