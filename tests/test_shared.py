"""Tests for the shared layer. No model, no network, no dataset."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.datasets import Task, load  # noqa: E402
from shared.execute import extract_code, run  # noqa: E402

GOOD = "def add(a, b):\n    return a + b\n"
TESTS = ["assert add(1, 2) == 3", "assert add(0, 0) == 0"]


# --- execution -----------------------------------------------------------------------


def test_correct_code_passes():
    assert run(GOOD, TESTS).status == "pass"


def test_wrong_code_fails_an_assert():
    assert run("def add(a, b):\n    return a - b\n", TESTS).status == "fail"


def test_crash_is_error_not_fail():
    # The distinction matters: a crash is the tests catching something without
    # having tested for it.
    assert run("x = 1\n", TESTS).status == "error"


def test_infinite_loop_times_out():
    assert run("def add(a, b):\n    while True: pass\n", TESTS, timeout=3).status == "timeout"


def test_tests_may_be_a_bare_string():
    assert run(GOOD, "assert add(1, 1) == 2").status == "pass"


def test_setup_runs_after_the_solution():
    # Setup often instantiates a class the solution defines; running it first
    # would raise NameError on perfectly good code.
    code = "class Box:\n    def __init__(self, v):\n        self.v = v\n"
    assert run(code, ["assert b.v == 7"], setup="b = Box(7)").status == "pass"


def test_crlf_source_does_not_become_a_syntax_error():
    # Windows newline translation turns CRLF into CR CR LF and breaks backslash
    # line-continuations. This is the case that caught it.
    code = "def add(a, b):\r\n    x = a + \\\r\n        b\r\n    return x\r\n"
    assert run(code, ["assert add(1, 2) == 3"]).status == "pass"


# --- code extraction -----------------------------------------------------------------


def test_extracts_fenced_python():
    assert extract_code("Sure!\n```python\ndef f(): pass\n```\nDone") == "def f(): pass"


def test_extracts_fenced_without_language():
    assert extract_code("```\ndef f(): pass\n```") == "def f(): pass"


def test_unfenced_response_is_returned_whole():
    assert extract_code("def f(): pass") == "def f(): pass"


def test_empty_response_is_empty():
    assert extract_code("") == ""
    assert extract_code(None) == ""


# --- task model ----------------------------------------------------------------------


def test_is_mbpp_flag():
    assert Task("mbpp", "mbpp/1", "p", "c", "f", ()).is_mbpp
    assert not Task("humaneval", "HumanEval/0", "p", "c", "f", ()).is_mbpp


def test_unknown_benchmark_rejected():
    import pytest

    with pytest.raises(ValueError, match="unknown benchmark"):
        load("nonexistent")


# --- pass@k --------------------------------------------------------------------------


def test_pass_at_k_estimator():
    sys.path.insert(
        0, str(Path(__file__).resolve().parent.parent / "projects" / "06_temperature_pass_at_k")
    )
    from run import pass_at_k

    # All samples correct -> certain.
    assert pass_at_k(10, 10, 1) == 1.0
    # None correct -> impossible.
    assert pass_at_k(10, 0, 5) == 0.0
    # 1 of 10 correct, drawing 1: exactly 10%.
    assert abs(pass_at_k(10, 1, 1) - 0.1) < 1e-9
    # Drawing more samples can only help.
    assert pass_at_k(10, 3, 5) > pass_at_k(10, 3, 1)


def test_pass_at_k_when_k_exceeds_failures():
    # If fewer than k samples are wrong, any draw of k must contain a correct one.
    assert pass_at_k_import()(10, 8, 5) == 1.0


def pass_at_k_import():
    sys.path.insert(
        0, str(Path(__file__).resolve().parent.parent / "projects" / "06_temperature_pass_at_k")
    )
    from run import pass_at_k

    return pass_at_k
