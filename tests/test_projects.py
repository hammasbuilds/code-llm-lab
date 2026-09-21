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
