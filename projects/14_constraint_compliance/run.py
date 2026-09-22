"""Does it obey the constraint, and what does obeying cost?

House rules are given to a model the same way they are given to a new hire: as a sentence.
"Use only the standard library." "No recursion in this codebase." "Type-annotate everything."

Two things can go wrong and they need different fixes. The model can ignore the rule, or it
can obey the rule and break the code. A single pass rate cannot tell them apart, so both are
measured on every task:

- **compliance** - is the constraint actually satisfied, checked on the AST
- **pass@1**     - does it still pass the tests

Six constraints, each mechanically checkable, so there is no judge in the loop:

    no_recursion · no_imports · no_comprehensions · no_builtin_sort
    type_hints · single_return

The interesting cell is high compliance with a drop in pass rate: that is the model doing
what it was told and paying for it, which is a different problem from a rule being ignored.

    python run.py --limit 150
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

BASE = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}
{rule}
Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""


def _funcs(tree: ast.AST) -> list[ast.FunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]


def _target(tree: ast.AST, entry_point: str | None) -> ast.FunctionDef | None:
    """The function the task is about, not merely the first one defined.

    1.5% of submissions define a helper before the answer - `sum_of_divisors` above
    `amicable_numbers_sum`, `kadane` above `max_sub_array_sum_repeated`. Checking `fns[0]`
    then judges the helper, so a model that annotated exactly what it was asked to annotate
    is recorded as non-compliant because its untyped scratch function came first.
    """
    fns = _funcs(tree)
    if not fns:
        return None
    if entry_point:
        for fn in fns:
            if fn.name == entry_point:
                return fn
    # No entry point given, or the model never defined it: the answer is conventionally
    # last, after whatever it needed to build first.
    return fns[-1]


def _own_returns(fn: ast.FunctionDef) -> int:
    """Returns belonging to `fn` itself, not to functions nested inside it."""
    count = 0
    for node in ast.walk(fn):
        if isinstance(node, ast.Return):
            count += 1
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node is not fn:
            count -= sum(isinstance(k, ast.Return) for k in ast.walk(node))
    return count


def _no_recursion(tree: ast.AST) -> bool:
    for fn in _funcs(tree):
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == fn.name
            ):
                return False
    return True


def _no_imports(tree: ast.AST) -> bool:
    return not any(isinstance(n, ast.Import | ast.ImportFrom) for n in ast.walk(tree))


def _no_comprehensions(tree: ast.AST) -> bool:
    kinds = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    return not any(isinstance(n, kinds) for n in ast.walk(tree))


def _no_builtin_sort(tree: ast.AST) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == "sorted":
                return False
            if isinstance(f, ast.Attribute) and f.attr == "sort":
                return False
    return True


def _type_hints(tree: ast.AST, entry_point: str | None = None) -> bool:
    fn = _target(tree, entry_point)
    if fn is None:
        return False
    args = [a for a in fn.args.args if a.arg not in ("self", "cls")]
    return bool(fn.returns) and all(a.annotation for a in args)


def _single_return(tree: ast.AST, entry_point: str | None = None) -> bool:
    fn = _target(tree, entry_point)
    if fn is None:
        return False
    # "Exactly one", as the prompt asks. A function with no return at all satisfies "at
    # most one" but is not what was requested, and the old check accepted it.
    return _own_returns(fn) == 1


CONSTRAINTS = {
    "no_recursion": ("\nDo not use recursion.\n", _no_recursion),
    "no_imports": ("\nDo not import anything. Use only built-ins.\n", _no_imports),
    "no_comprehensions": (
        "\nDo not use any list, set, dict or generator comprehension.\n",
        _no_comprehensions,
    ),
    "no_builtin_sort": (
        "\nDo not use sorted() or .sort(). Implement any ordering yourself.\n",
        _no_builtin_sort,
    ),
    "type_hints": (
        "\nAnnotate every parameter and the return value with a type.\n",
        _type_hints,
    ),
    "single_return": ("\nThe function must have exactly one return statement.\n", _single_return),
}


def complies(name: str, code: str, entry_point: str | None = None) -> bool | None:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    check = CONSTRAINTS[name][1]
    # Only the two whole-function checks need to know which function is the answer; the
    # rest are properties of the whole submission.
    if check in (_type_hints, _single_return):
        return check(tree, entry_point)
    return check(tree)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if not available(args.model):
        print(f"{args.model} not available")
        return 1

    tasks = load("mbpp", args.limit)
    n = len(tasks)
    print(f"mbpp: {n} tasks x {len(CONSTRAINTS) + 1} arms, model {args.model}\n")

    # The unconstrained arm is the control, and it is also measured for compliance - a
    # constraint the model already satisfies by habit is not evidence it followed an
    # instruction, and without this column the two are indistinguishable.
    arms = {"none": ("", None), **CONSTRAINTS}
    summary: dict[str, dict] = {}

    for arm, (rule, _) in arms.items():
        t0 = time.time()
        raws = generate_many(
            [BASE.format(prompt=t.prompt, test=t.tests[0], rule=rule) for t in tasks],
            model=args.model,
            temperature=0.0,
            workers=args.workers,
            progress=arm,
        )
        codes = [extract_code(r) if r else "" for r in raws]
        outs = run_many(
            [(c, list(t.tests), t.setup) for c, t in zip(codes, tasks, strict=True)],
            args.workers,
        )
        passed = sum(o.passed for o in outs) / n

        row = {"pass_at_1": passed}
        if arm == "none":
            row["baseline_compliance"] = {
                name: sum(
                    complies(name, c, t.entry_point) is True
                    for c, t in zip(codes, tasks, strict=True)
                )
                / n
                for name in CONSTRAINTS
            }
        else:
            verdicts = [complies(arm, c, t.entry_point) for c, t in zip(codes, tasks, strict=True)]
            row["compliance"] = sum(v is True for v in verdicts) / n
            row["unparseable"] = sum(v is None for v in verdicts)
            # Complied AND still works - the only cell that is actually a success.
            row["compliant_and_passing"] = (
                sum((v is True) and o.passed for v, o in zip(verdicts, outs, strict=True)) / n
            )
        summary[arm] = row

        if arm == "none":
            print(f"  {arm:19} pass@1 {passed:6.1%}   (control)  [{time.time() - t0:.0f}s]")
        else:
            print(
                f"  {arm:19} pass@1 {passed:6.1%}   complied {row['compliance']:6.1%}   "
                f"both {row['compliant_and_passing']:6.1%}  [{time.time() - t0:.0f}s]"
            )

    base = summary["none"]["pass_at_1"]
    baseline_comp = summary["none"]["baseline_compliance"]

    print("\n" + "=" * 84)
    print(f"CONSTRAINT COMPLIANCE - {n} MBPP tasks, {args.model}")
    print("=" * 84)
    print(f"  unconstrained pass@1: {base:.1%}\n")
    print(
        f"  {'constraint':20} {'already':>8} {'complied':>9} {'pass@1':>8} "
        f"{'vs control':>11} {'both':>7}"
    )
    for name in CONSTRAINTS:
        r = summary[name]
        print(
            f"  {name:20} {baseline_comp[name]:8.0%} {r['compliance']:9.0%} "
            f"{r['pass_at_1']:8.1%} {r['pass_at_1'] - base:+11.1%} "
            f"{r['compliant_and_passing']:7.0%}"
        )
    print(
        "\n  'already' is how often the unconstrained control satisfies the rule by habit.\n"
        "  A constraint with a high 'already' column proves little when it is obeyed."
    )

    ignored = [k for k in CONSTRAINTS if summary[k]["compliance"] < 0.8]
    costly = [k for k in CONSTRAINTS if summary[k]["pass_at_1"] < base - 0.05]
    if ignored:
        print(f"\n  obeyed less than 80% of the time : {', '.join(ignored)}")
    if costly:
        print(
            f"  cost more than 5 points of pass@1: {', '.join(costly)}\n"
            "  <- these are obeyed and expensive, which is a different problem from ignored"
        )

    (HERE / "results.json").write_text(
        json.dumps(
            {
                **stamp(models=args.model, benchmark="mbpp", n=n),
                "unconstrained_pass_at_1": base,
                "arms": summary,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {HERE / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
