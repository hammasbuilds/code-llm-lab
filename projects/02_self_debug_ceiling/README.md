<h1 align="center">self-debug-ceiling</h1>
<p align="center"><i>How many rounds of test feedback are worth paying for?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-150-blue" alt="">
  <img src="https://img.shields.io/badge/rounds-5-green" alt="">
  <img src="https://img.shields.io/badge/oracle-real%20tests-brightgreen" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Show the model its failing test output and let it try again. Everyone builds this
loop; almost nobody publishes where it stops helping.

Unlike a revision loop judged by another model, **the oracle here is real** &mdash; a
failing assert is ground truth, so "did the extra round help" is a fact.

## Result

```
round 1: +117 solved   cumulative 78.0%
round 2: +  1 solved   cumulative 78.7%
round 3: +  0 solved   cumulative 78.7%
round 4: +  0 solved   cumulative 78.7%
round 5: +  0 solved   cumulative 78.7%
```

**Rounds 1&ndash;2 captured 100.0% of everything the loop ever
achieved. Rounds 3&ndash;5 added 0 tasks for 60% of the compute.**

The tasks still failing after round one were not tasks the model was one nudge from
solving. They were tasks it could not do, and showing it the error five times did not
change that.

A second project here agrees from the other direction:
[repair vs rewrite](../04_repair_vs_rewrite) found 93.3% of first-attempt failures survive
*both* a repair and a from-scratch rewrite.

## Running it

```bash
python run.py --limit 150 --rounds 5
```

## Limits

- The curve cannot show a fix that passes the tests and is still wrong. Feedback-driven
  repair optimises for the tests it is shown &mdash; see
  [mbpp-false-accepts](https://github.com/hammasbuilds/mbpp-false-accepts) for how thin
  those tests are.
- MBPP tasks are short. Where a first attempt lands closer to right, later rounds may pay.
