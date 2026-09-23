<h1 align="center">test-first</h1>
<p align="center"><i>Does writing the tests first help the model write the code?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-972-blue" alt="">
  <img src="https://img.shields.io/badge/attributable%2520to%2520tests--3.6pp-b8860b" alt="">
  <img src="https://img.shields.io/badge/harness%2520swing%2520found-54pp-b91c1c" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Test-driven development is advice about people: writing the test first forces you to
decide what the function does before deciding how. Whether that transfers to a model is an
empirical question, and it is the kind of thing a team adopts on the strength of the analogy.

Four arms, and the third one is the control that makes the answer mean anything:

```
direct       just write the function
plan         describe the approach first, then write it
tests_then   write tests first, then the implementation
tests_seen   write tests, then implement in a FRESH context given only those tests
```

## Result

All 972 MBPP tasks, four arms.

```
direct        80.3%           just write the function
plan          78.3%  -2.1%    think out loud first, then write it
tests_then    74.7%  -5.7%    write tests first, then the function
tests_seen    78.4%  -2.0%    the same tests, carried into a fresh context

writing tests first is worth : -5.7%
any preamble at all is worth : -2.1%
attributable to the *tests*  : -3.6%
```

**Writing tests first costs 5.7 points.** But `plan` - think out loud about anything, then
write the function - costs 2.1 on its own, so most of a naive reading would be attributing
to TDD what is really the cost of generating a preamble at all.

**The `plan` arm is the control that makes this project worth running.** Without it the
finding is "tests-first is worse", which is true and uninformative. With it the finding is
that only **3.6 points** belong to the tests, and 2.1 belong to filling the context with
anything before answering.

**Carrying the tests into a fresh context recovers most of it.** `tests_seen` hands the model
the same tests it wrote, in a clean context, and scores 78.4% - 3.7 points better than
generating them inline. So the damage is not from having tests in view; it is from having
produced them in the same breath.

The response lengths say the same thing from another angle:

```
direct      184 chars
tests_seen  170
plan      1,131
tests_then 1,678
```

The two cheap arms are the two short ones, and `tests_seen` - which has tests available but
did not write them - is the shortest of all. **On MBPP, the TDD framing does negative work**,
and the mechanism is the preamble rather than the tests.

### The number this project reported before three harness bugs were fixed

This read **17.0%** on the `tests_then` arm at one point, against 80.3% direct - a 63-point
gap that would have been a spectacular finding. It was three bugs in the extraction and
scoring path, fixed in an earlier pass, and the arm moved 54 points without the model's
output changing at all. `strip_self_tests` in `shared/execute.py` exists because of it: a
prompt that asks for tests *and* an implementation gets both in one block, and submitting
the block whole runs the model's own tests above its `def`.

## Running it

```bash
python run.py --limit 972
```

## Limits

- MBPP tasks are small enough to hold in one thought. TDD's claimed benefit is about managing
  complexity, and there is little here to manage.
- `tests_then` produces 1,770 characters against `direct`'s 193. Part of the gap may be the
  token budget rather than the framing, though only 4 of 200 responses were truncated.
