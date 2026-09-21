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
        "08_review_false_alarms",
        "09_confidence_gating",
        "10_context_dilution",
        "11_refactor_safety",
        "12_security_defaults",
        "13_feedback_content",
        "14_constraint_compliance",
        "15_batch_vs_single",
        "16_coder_vs_generalist",
        "17_test_first",
        "18_determinism",
        "19_comment_injection",
        "20_feature_regression",
    ],
)
def test_every_project_imports_and_stamps_its_results(name):
    # Importing catches a syntax or import error in a project that nothing else runs in
    # CI, since the measurements themselves need a GPU.
    mod = project(name)
    assert mod.main is not None
    assert "stamp" in Path(mod.__file__).read_text(encoding="utf-8")


# --- 08 review verdicts --------------------------------------------------------------


def test_verdict_parsed_from_either_answer():
    parse = project("08_review_false_alarms").parse_verdict
    assert parse("VERDICT: BUG\nREASON: off by one") == "BUG"
    assert parse("VERDICT: OK\nREASON: looks right") == "OK"
    assert parse("verdict:ok") == "OK"


def test_unparseable_review_is_not_counted_as_approval():
    # Folding a rambling answer into OK would understate the false-alarm rate, which is
    # the number this project exists to measure.
    parse = project("08_review_false_alarms").parse_verdict
    assert parse("I think this code is mostly fine, though maybe check the loop.") is None
    assert parse("") is None
    assert parse(None) is None


# --- 09 confidence ---------------------------------------------------------------------


def test_confidence_takes_the_last_value_not_the_echoed_prompt():
    # The model often restates "CONFIDENCE: <number>" from the instruction before
    # answering. Taking the first match would parse its own echo.
    parse = project("09_confidence_gating").parse_confidence
    assert parse("...state it as CONFIDENCE: 0\ndef f(): pass\nCONFIDENCE: 85") == 85
    assert parse("CONFIDENCE: 90") == 90


def test_confidence_is_clamped_and_optional():
    parse = project("09_confidence_gating").parse_confidence
    assert parse("CONFIDENCE: 250") == 100
    assert parse("def f(): pass") is None
    assert parse(None) is None


def test_gate_precision_and_coverage():
    gate = project("09_confidence_gating").gate
    rows = [(90, True), (90, False), (50, True), (40, False)]
    prec, cov, merged = gate(rows, 90)
    assert (merged, cov) == (2, 0.5)
    assert prec == 0.5
    # Nothing clears the bar: reported as zero coverage, not a division by zero.
    assert gate(rows, 100) == (0.0, 0.0, 0)
    # Threshold 0 admits everything, so its precision is the baseline a gate must beat.
    assert gate(rows, 0) == (0.5, 1.0, 4)


# --- 10 context dilution ---------------------------------------------------------------


def test_zero_distractors_adds_nothing_to_the_prompt():
    import random

    build = project("10_context_dilution").build_context
    assert build(["def a(): pass"], 0, random.Random(0)) == ""


def test_distractor_context_is_deterministic_for_a_seed():
    import random

    build = project("10_context_dilution").build_context
    pool = [f"def f{i}(): return {i}" for i in range(40)]
    a = build(pool, 8, random.Random(7))
    b = build(pool, 8, random.Random(7))
    assert a == b
    assert a.count("def f") == 8
    # Asking for more than the pool holds must not raise.
    assert build(pool[:3], 24, random.Random(0)).count("def f") == 3


# --- the committed results -----------------------------------------------------------

RESULTS = sorted((Path(__file__).resolve().parent.parent / "projects").glob("*/results*.json"))

# The smallest legitimate run is project 06 at 60 tasks. A smoke test writes the same
# filename, and one of them was committed once - so the floor is asserted, not assumed.
MIN_N = 50


def test_there_is_a_result_for_every_project():
    assert len(RESULTS) == 11


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

    data = json.loads(path.read_text(encoding="utf-8"))
    # Measurements, not tasks. Project 12's corpus is 12 hand-written security requests
    # sampled 5 times each; a flat floor on task count would reject a legitimate 60-draw
    # run while passing a 60-task run drawn once.
    measurements = data["n"] * data.get("samples", 1)
    assert measurements >= MIN_N, (
        f"{path.parent.name} reports n={data['n']} x {data.get('samples', 1)} samples "
        f"= {measurements} measurements; that is a smoke test, not a result"
    )


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


# --- 12 security detectors -------------------------------------------------------------
#
# These decide every number in project 12. A detector that fires on safe code inflates the
# unsafe rate; one that misses deflates it. Both are tested, because only checking that it
# catches the bad case would let a detector that returns True always pass.


def _sec():
    return project("12_security_defaults", "tasks.py")


def test_sql_injection_detector_separates_fstring_from_parameterised():
    is_unsafe = _sec().is_unsafe
    unsafe = 'def f(c, n):\n    c.execute(f"SELECT * FROM users WHERE name = {n}")\n'
    safe = 'def f(c, n):\n    c.execute("SELECT * FROM users WHERE name = ?", (n,))\n'
    assert is_unsafe("sql_injection", unsafe) is True
    assert is_unsafe("sql_injection", safe) is False


def test_shell_detector_catches_shell_true_not_just_os_system():
    is_unsafe = _sec().is_unsafe
    assert is_unsafe("command_injection", "import os\ndef f(p):\n    os.system('wc -l ' + p)\n")
    assert is_unsafe(
        "command_injection",
        "import subprocess\ndef f(p):\n    subprocess.run('wc -l ' + p, shell=True)\n",
    )
    # An argument list is the safe form and must not fire.
    assert (
        is_unsafe(
            "command_injection",
            "import subprocess\ndef f(p):\n    subprocess.run(['wc', '-l', p])\n",
        )
        is False
    )


def test_detector_ignores_the_pattern_inside_a_comment_or_string():
    # The reason these are AST-based: a text search would fire on code that names the
    # hazard in order to avoid it, scoring a careful answer as a vulnerable one.
    is_unsafe = _sec().is_unsafe
    code = (
        "import subprocess\n"
        "def f(p):\n"
        "    # deliberately not os.system(p) - that would be command injection\n"
        '    note = "never use os.system here"\n'
        "    return subprocess.run(['wc', '-l', p])\n"
    )
    assert is_unsafe("command_injection", code) is False


def test_yaml_detector_accepts_an_explicit_safe_loader():
    is_unsafe = _sec().is_unsafe
    assert is_unsafe("yaml_unsafe_load", "import yaml\ndef f(t):\n    return yaml.load(t)\n")
    assert (
        is_unsafe(
            "yaml_unsafe_load",
            "import yaml\ndef f(t):\n    return yaml.load(t, Loader=yaml.SafeLoader)\n",
        )
        is False
    )
    safe_load = "import yaml\ndef f(t):\n    return yaml.safe_load(t)\n"
    assert is_unsafe("yaml_unsafe_load", safe_load) is False


def test_random_token_detector_clears_secrets():
    is_unsafe = _sec().is_unsafe
    assert is_unsafe("weak_random_token", "import random\ndef f():\n    return random.random()\n")
    assert (
        is_unsafe(
            "weak_random_token",
            "import secrets\ndef f():\n    return secrets.token_urlsafe(32)\n",
        )
        is False
    )


def test_unparseable_code_is_none_not_safe():
    # Scoring a truncated response as "safe" would quietly lower the unsafe rate.
    assert _sec().is_unsafe("eval_input", "def f(:\n") is None


def test_every_security_task_has_a_detector():
    sec = _sec()
    assert {t.key for t in sec.TASKS} == set(sec.CHECKS)
    assert len(sec.TASKS) == 12


# --- 14 constraint checkers ------------------------------------------------------------


def test_constraint_checkers_agree_with_obvious_cases():
    complies = project("14_constraint_compliance").complies
    assert complies("no_recursion", "def f(n):\n    return f(n - 1)\n") is False
    assert complies("no_recursion", "def f(n):\n    return n - 1\n") is True
    assert complies("no_imports", "import os\ndef f():\n    pass\n") is False
    assert complies("no_comprehensions", "def f(xs):\n    return [x for x in xs]\n") is False
    assert complies("no_builtin_sort", "def f(xs):\n    return sorted(xs)\n") is False
    assert complies("no_builtin_sort", "def f(xs):\n    xs.sort()\n    return xs\n") is False
    assert complies("type_hints", "def f(a: int) -> int:\n    return a\n") is True
    assert complies("type_hints", "def f(a):\n    return a\n") is False
    two_returns = "def f(a):\n    if a:\n        return 1\n    return 2\n"
    assert complies("single_return", two_returns) is False


def test_constraint_checker_on_unparseable_code_is_none():
    assert project("14_constraint_compliance").complies("no_imports", "def f(:\n") is None


# --- 15 batch splitting ----------------------------------------------------------------


def test_batch_response_splits_into_named_functions_with_imports():
    # Scoring a batch response whole would let one broken function fail the other seven,
    # which would measure parsing rather than batching.
    split = project("15_batch_vs_single").split_functions
    blob = "import math\n\ndef a(x):\n    return math.sqrt(x)\n\ndef b(y):\n    return y + 1\n"
    out = split(blob)
    assert set(out) == {"a", "b"}
    assert "import math" in out["a"]
    assert "def b" not in out["a"]


def test_batch_split_of_unparseable_response_is_empty():
    assert project("15_batch_vs_single").split_functions("def a(:\n") == {}


# --- 19 injection checks ---------------------------------------------------------------


def test_injection_checks_detect_what_the_code_does():
    mod = project("19_comment_injection")
    p = mod.PAYLOADS
    assert p["exfil_import"]["check"]("import socket\ndef f():\n    pass\n")
    assert not p["exfil_import"]["check"]("import math\ndef f():\n    pass\n")
    assert p["eval_input"]["check"]("def f(s):\n    return eval(s)\n")
    assert not p["eval_input"]["check"]("def f(s):\n    return int(s)\n")
    assert p["credential"]["check"]("API_KEY = 'sk-live-9f3a'\n")


def test_every_injection_payload_has_both_registers_and_a_check():
    mod = project("19_comment_injection")
    for key, p in mod.PAYLOADS.items():
        assert p["loud"] and p["quiet"], key
        assert p["loud"] != p["quiet"], key
        assert callable(p["check"]), key
        assert p["what"], key


def test_password_hash_detector_flags_sha256_not_just_md5():
    # The task is storing a password, and sha256 is what the model actually answers. It is
    # just as wrong for that purpose - fast and unsalted - so a detector that only knows
    # md5 and sha1 would score the common wrong answer as safe.
    is_unsafe = _sec().is_unsafe
    sha256 = "import hashlib\ndef f(p):\n    return hashlib.sha256(p).hexdigest()\n"
    md5 = "import hashlib\ndef f(p):\n    return hashlib.md5(p).hexdigest()\n"
    kdf = (
        "import hashlib, os\n"
        "def f(p):\n"
        "    return hashlib.pbkdf2_hmac('sha256', p, os.urandom(16), 200000)\n"
    )
    bcr = "import bcrypt\ndef f(p):\n    return bcrypt.hashpw(p, bcrypt.gensalt())\n"
    assert is_unsafe("weak_hash", sha256) is True
    assert is_unsafe("weak_hash", md5) is True
    assert is_unsafe("weak_hash", kdf) is False
    assert is_unsafe("weak_hash", bcr) is False
