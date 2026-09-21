"""Tests for the per-project analysis code. No model, no network, no dataset.

The shared layer was covered; the seven `run.py` files were not, even though that is where
the measurements actually happen. A prompt builder that drops the test line, or an assert
filter that keeps a truncated line, changes a published number without failing anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _loader import project  # noqa: E402

from shared.datasets import Task  # noqa: E402
from shared.provenance import stamp  # noqa: E402

REFERENCE = "def add(a, b):\n    return a + b\n"

MBPP = Task(
    benchmark="mbpp",
    task_id="mbpp/1",
    prompt="Write a function to add two numbers.",
    reference=REFERENCE,
    entry_point="add",
    tests=("assert add(1, 2) == 3", "assert add(0, 0) == 0"),
)
HUMANEVAL = Task(
    benchmark="humaneval",
    task_id="humaneval/1",
    prompt='def add(a, b):\n    """Add two numbers."""\n',
    reference=REFERENCE,
    entry_point="add",
    tests=("assert add(1, 2) == 3",),
)


# --- the loader itself ---------------------------------------------------------------


def test_each_project_loads_as_its_own_module():
    # The bug this guards: importing the bare name `run` from two project directories
    # returns the same cached module, so a test silently asserts against the wrong file.
    a = project("01_coder_size_curve")
    b = project("06_temperature_pass_at_k")
    assert a is not b
    assert a.__file__ != b.__file__


# --- 01 prompt construction ----------------------------------------------------------


def test_mbpp_prompt_carries_the_test_line():
    # MBPP's description does not say the function's name. Without the assert the model
    # has to guess it, and the run measures naming luck rather than the model.
    out = project("01_coder_size_curve").build_prompt(MBPP)
    assert "assert add(1, 2) == 3" in out
    assert MBPP.prompt in out


def test_humaneval_prompt_is_a_completion_not_a_description():
    out = project("01_coder_size_curve").build_prompt(HUMANEVAL)
    assert HUMANEVAL.prompt in out
    # HumanEval ships the signature, so the test must not be pasted in as an example.
    assert "assert add(1, 2) == 3" not in out


# --- 02 retry prompt -----------------------------------------------------------------


def test_first_prompt_differs_by_benchmark():
    mod = project("02_self_debug_ceiling")
    assert mod.first_prompt(MBPP) != mod.first_prompt(HUMANEVAL)
    assert MBPP.tests[0] in mod.first_prompt(MBPP)


# --- 03 assert filtering -------------------------------------------------------------


def test_truncated_assert_is_dropped_not_fatal():
    # The real failure: the token limit cuts the last assert mid-bracket. Parsing the
    # suite as one unit makes it a SyntaxError and drops the whole task from the sample.
    parse = project("03_tests_that_kill").parse_asserts
    kept = parse("assert f(1) == 2\nassert f([1,\n")
    assert kept == ["assert f(1) == 2"]


def test_prose_between_asserts_is_ignored():
    parse = project("03_tests_that_kill").parse_asserts
    raw = "Here are the tests:\nassert f(1) == 2\nThat covers it.\nassert f(2) == 4"
    assert parse(raw) == ["assert f(1) == 2", "assert f(2) == 4"]


def test_duplicate_asserts_are_collapsed():
    # Counting the same assert twice would inflate the suite size the kill rate is
    # reported against.
    parse = project("03_tests_that_kill").parse_asserts
    assert parse("assert f(1) == 2\nassert f(1) == 2") == ["assert f(1) == 2"]


def test_assert_limit_is_honoured():
    parse = project("03_tests_that_kill").parse_asserts
    raw = "\n".join(f"assert f({i}) == {i}" for i in range(50))
    assert len(parse(raw, limit=7)) == 7


# --- 05 prompt shapes ----------------------------------------------------------------


def test_all_five_shapes_build_and_differ():
    mod = project("05_prompt_shape_variance")
    built = {s: mod.build(s, MBPP) for s in mod.SHAPES}
    assert len(built) == 5
    # The claim the project rests on is that only the wording changes. Identical shapes
    # would make the measured spread meaningless.
    assert len(set(built.values())) == 5


def test_every_shape_carries_the_task_and_its_test():
    mod = project("05_prompt_shape_variance")
    for shape in mod.SHAPES:
        out = mod.build(shape, MBPP)
        assert MBPP.prompt in out, shape
        # `docstring` rewrites the assert into a doctest, so match the expression.
        assert "add(1, 2) == 3" in out, shape


def test_docstring_shape_strips_the_assert_keyword():
    mod = project("05_prompt_shape_variance")
    out = mod.build("docstring", MBPP)
    assert ">>> add(1, 2) == 3" in out
    assert "assert" not in out


# --- 06 pass@k -----------------------------------------------------------------------


def test_pass_at_k_is_monotonic_in_k():
    pass_at_k = project("06_temperature_pass_at_k").pass_at_k
    vals = [pass_at_k(10, 3, k) for k in (1, 2, 5, 10)]
    assert vals == sorted(vals)


def test_pass_at_k_matches_the_closed_form():
    # 1 - C(n-c, k)/C(n, k) computed the other way round, as a check on the loop.
    import math

    pass_at_k = project("06_temperature_pass_at_k").pass_at_k
    for n, c, k in [(10, 3, 2), (5, 1, 3), (20, 7, 4)]:
        expect = 1 - math.comb(n - c, k) / math.comb(n, k)
        assert abs(pass_at_k(n, c, k) - expect) < 1e-9


# --- provenance ----------------------------------------------------------------------


def test_stamp_records_what_is_needed_to_reproduce():
    s = stamp(models="qwen2.5-coder:14b", benchmark="mbpp", n=250)
    assert s["models"] == ["qwen2.5-coder:14b"]  # a bare string is wrapped
    assert s["n"] == 250
    for field in ("benchmark", "temperature", "samples", "seeds", "python", "commit", "run_at"):
        assert field in s


def test_stamp_extra_fields_are_merged():
    s = stamp(models=["a", "b"], benchmark="mbpp", n=1, extra={"rounds": 5})
    assert s["models"] == ["a", "b"]
    assert s["rounds"] == 5


@pytest.mark.parametrize(
    "name",
    [
        "01_coder_size_curve",
        "02_self_debug_ceiling",
        "03_tests_that_kill",
        "04_repair_vs_rewrite",
        "05_prompt_shape_variance",
        "06_temperature_pass_at_k",
        "07_docstring_roundtrip",
    ],
)
def test_every_project_imports_and_stamps_its_results(name):
    # Importing catches a syntax or import error in a project that nothing else runs in
    # CI, since the measurements themselves need a GPU.
    mod = project(name)
    assert mod.main is not None
    assert "stamp" in Path(mod.__file__).read_text(encoding="utf-8")


# --- the committed results -----------------------------------------------------------

RESULTS = sorted((Path(__file__).resolve().parent.parent / "projects").glob("*/results*.json"))

# The smallest legitimate run is project 06 at 60 tasks. A smoke test writes the same
# filename, and one of them was committed once - so the floor is asserted, not assumed.
MIN_N = 50


def test_there_is_a_result_for_every_project():
    assert len(RESULTS) == 7


@pytest.mark.parametrize("path", RESULTS, ids=lambda p: p.parent.name)
def test_committed_result_carries_its_provenance(path):
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    for field in ("models", "benchmark", "n", "temperature", "samples", "run_at"):
        assert field in data, f"{path.parent.name} is missing {field}"
    assert data["models"] and all(isinstance(m, str) for m in data["models"])


@pytest.mark.parametrize("path", RESULTS, ids=lambda p: p.parent.name)
def test_committed_result_is_not_a_smoke_test(path):
    import json

    n = json.loads(path.read_text(encoding="utf-8"))["n"]
    assert n >= MIN_N, f"{path.parent.name} reports n={n}; that is a smoke test, not a result"


# --- the results are internally consistent -------------------------------------------
#
# Every headline in the README is derived from these files, so a file that contradicts
# itself means a published number is wrong. These check the arithmetic each project's
# claim rests on, without hardcoding the README's text - which would only break whenever
# a run is repeated.


def _load(rel: str) -> dict:
    import json

    return json.loads((Path(__file__).resolve().parent.parent / "projects" / rel).read_text())


def test_01_buckets_partition_the_benchmark():
    d = _load("01_coder_size_curve/results_mbpp.json")
    b = {k: set(v) for k, v in d["buckets"].items()}
    assert sum(len(v) for v in b.values()) == d["n"]
    # The headline is "the 3B already handles 75.8% of what either size can solve", which
    # is only true if the buckets are disjoint.
    for x, y in [("both", "big_only"), ("both", "small_only"), ("big_only", "small_only")]:
        assert not b[x] & b[y], f"{x} and {y} overlap"
    small = len(b["both"]) + len(b["small_only"])
    big = len(b["both"]) + len(b["big_only"])
    assert abs(small / d["n"] - d["pass_at_1"]["qwen2.5-coder:3b"]) < 1e-9
    assert abs(big / d["n"] - d["pass_at_1"]["qwen2.5-coder:14b"]) < 1e-9


def test_02_cumulative_matches_the_per_round_gains():
    d = _load("02_self_debug_ceiling/results_mbpp.json")
    rounds = d["per_round_newly_solved"]
    assert len(rounds) == d["rounds"]
    for i, cum in enumerate(d["cumulative_pass"]):
        assert abs(cum - sum(rounds[: i + 1]) / d["n"]) < 1e-9
    assert sum(rounds) <= d["n"]


def test_03_kill_counts_cannot_exceed_the_mutants():
    d = _load("03_tests_that_kill/results.json")
    for arm, a in d["arms"].items():
        assert a["suites"] == d["n"], arm
        assert abs(a["validity"] - a["valid"] / a["suites"]) < 1e-9, arm
        assert a["scored"] <= a["valid"], arm
        assert a["model_killed"] <= a["mutants"], arm
        assert a["mbpp_killed"] <= a["mutants"], arm


def test_04_arms_and_neither_account_for_every_failure():
    d = _load("04_repair_vs_rewrite/results.json")
    f = d["first_attempt_failures"]
    assert len(d["per_task"]) == f
    union = d["repair_fixed"] + d["rewrite_fixed"] - d["both"]
    # The headline is the 93.3% that survived both arms.
    assert union + d["neither"] == f
    assert d["both"] <= min(d["repair_fixed"], d["rewrite_fixed"])


def test_05_flip_count_is_the_gap_between_any_and_all():
    d = _load("05_prompt_shape_variance/results.json")
    assert d["solved_by_all"] <= d["solved_by_any"] <= d["n"]
    assert d["flipped"] == d["solved_by_any"] - d["solved_by_all"]
    vals = list(d["pass_at_1"].values())
    assert abs(d["spread"] - (max(vals) - min(vals))) < 1e-9


def test_06_pass_at_k_rises_with_k_and_t0_is_flat():
    d = _load("06_temperature_pass_at_k/results.json")
    for t, row in d["pass_at_k"].items():
        ks = sorted(row, key=int)
        vals = [row[k] for k in ks]
        assert vals == sorted(vals), f"T={t} pass@k is not monotonic in k"
        assert d["mean_distinct_samples"][t] <= d["samples"]
    # The mechanism behind the whole finding: at T=0 every sample is the same string, so
    # pass@k cannot rise with k however large k gets.
    t0 = d["pass_at_k"]["0.0"]
    assert len(set(t0.values())) == 1
    assert d["mean_distinct_samples"]["0.0"] == 1.0


def test_07_the_two_arms_differ_by_exactly_gained_minus_lost():
    d = _load("07_docstring_roundtrip/results.json")
    n = d["n"]
    gained, lost = len(d["gained_in_roundtrip"]), len(d["lost_in_roundtrip"])
    assert not set(d["gained_in_roundtrip"]) & set(d["lost_in_roundtrip"])
    assert abs((d["roundtrip_pass"] - d["direct_pass"]) * n - (gained - lost)) < 1e-6
