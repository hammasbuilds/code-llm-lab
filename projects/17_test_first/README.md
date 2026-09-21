<h1 align="center">test-first</h1>
<p align="center"><i>Does writing the tests first help the model write the code?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-200-blue" alt="">
  <img src="https://img.shields.io/badge/attributable%2520to%2520tests-%252B1.0pp-b8860b" alt="">
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

```
direct        77.0%
plan          70.5%   (-6.5)
tests_then    71.5%   (-5.5)
tests_seen    77.0%   (+0.0)

writing tests first is worth : -5.5pp
any preamble at all is worth : -6.5pp
attributable to *tests*      : +1.0pp
```

**Writing tests first and simply thinking out loud first land within one point of each
other.** Whatever `tests_then` does, `plan` does the same. The TDD framing is doing no work
here - and both are *worse* than answering directly.

`tests_seen` is the separator: carrying the tests into a fresh context recovers the full
77.0%, which says the loss in the other two arms is about generating a long preamble, not
about the tests being unhelpful.

## The number was wrong three times before it was right

Worth recording, because the model's output never changed:

```
17.0%   scoring the FIRST fenced block - which the prompt asks to be the tests
47.0%   scoring the last block that defines something
71.5%   removing the model's own asserts from the submission
```

The last one is the subtle one. When the model puts asserts and the function in one block,
submitting the block runs its self-tests above the `def` - so a correct function fails with
`NameError`, and a wrong self-test rejects a right answer. This project's own premise is that
the model's tests are never the oracle; the harness was making them exactly that.

A 54-point swing, entirely in the scoring.

## Running it

```bash
python run.py --limit 200
```

## Limits

- MBPP tasks are small enough to hold in one thought. TDD's claimed benefit is about managing
  complexity, and there is little here to manage.
- `tests_then` produces 1,770 characters against `direct`'s 193. Part of the gap may be the
  token budget rather than the framing, though only 4 of 200 responses were truncated.
