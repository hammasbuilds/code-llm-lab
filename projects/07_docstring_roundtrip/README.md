<h1 align="center">docstring-roundtrip</h1>
<p align="center"><i>Code &rarr; prose &rarr; code. What survives?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-200-blue" alt="">
  <img src="https://img.shields.io/badge/drift-%2B32.5%25-9a6b3f" alt="">
  <img src="https://img.shields.io/badge/direction-wrong%20way-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Ask the model to describe the reference solution, hand that description to a fresh
context, and ask it to implement the function. Compare against implementing from MBPP's own
task description.

The expected result is loss &mdash; prose cannot carry everything code says.

## Result

```
from MBPP's description    : 48.0%
from the model's own prose : 80.5%
drift                      : +32.5%
```

**The roundtrip is 32.5% better**, which is the
opposite of the expected direction. 73 tasks are solved from
the code-derived description and not from MBPP's; only
8 go the other way.

The explanation is not that the model writes good documentation. **The description was
written with the answer in view.** It is a leak, not a spec. MBPP's descriptions average 78
characters; the model's average 445, and the extra characters
encode decisions &mdash; return type, edge-case behaviour, tie-breaking &mdash; that the
task sentence never made.

The practical consequence, stated plainly: **a docstring generated from an implementation
cannot be used to evaluate that implementation.** It is downstream of the code and agrees
with it by construction.

[tests-that-kill](../03_tests_that_kill) reaches the same conclusion from the other side:
only 16% of test suites written from those descriptions agree with the reference.

## Running it

```bash
python run.py --limit 200
```

## Limits

- Measures agreement with the reference, not correctness. Where MBPP's reference is itself
  wrong, both arms inherit that.
- One describe-then-implement hop. Repeated roundtrips would likely degrade.
