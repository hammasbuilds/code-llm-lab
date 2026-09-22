<h1 align="center">self-debug-ceiling</h1>
<p align="center"><i>How many rounds of test feedback are worth paying for?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-500-blue" alt="">
  <img src="https://img.shields.io/badge/rounds-5-green" alt="">
  <img src="https://img.shields.io/badge/rounds%25201--2-99.3%25-b91c1c" alt="">
  <img src="https://img.shields.io/badge/oracle-real%20tests-brightgreen" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Show the model its failing test output and let it try again. Everyone builds this
loop; almost nobody publishes where it stops helping.

Unlike a revision loop judged by another model, **the oracle here is real** &mdash; a
failing assert is ground truth, so "did the extra round help" is a fact.

## Result

500 MBPP tasks, five rounds, each round shown the **real traceback** of the failure.

```
round  newly solved  cumulative   share of total gain
    1           381      76.2%           94.5%
    2            19      80.0%            4.7%
    3             2      80.4%            0.5%
    4             1      80.6%            0.2%
    5             0      80.6%            0.0%
```

**Rounds 1&ndash;2 captured 99.3% of everything the loop ever achieved. Rounds 3&ndash;5
added 3 tasks &mdash; 0.6% of the benchmark &mdash; for 60% of the compute.**

The tasks still failing after round two were not tasks the model was one nudge from
solving. They were tasks it could not do, and showing it the error three more times did not
change that.

### This result was in doubt, and the doubt is now resolved

Every round of this loop used to be handed the string `AssertionError` and nothing else.
`Outcome.detail` is stderr's *last line*, which for an assertion failure is exactly that one
word &mdash; no file, no line, no source, no values. So the "feedback" was:

```
Running the tests gave:
AssertionError
```

A debug loop shown no information, plateauing after two rounds, is not evidence about debug
loops. It is evidence about the harness, and it is precisely the result that bug would
manufacture. The finding was marked unconfirmed rather than left standing.

Re-run with a real traceback, the plateau is unchanged: rounds 1&ndash;2 still capture
99.3%. **The ceiling is real, and it is not made of missing error messages.**

That matters because the same bug did *not* leave every project intact.
[feedback-content](../13_feedback_content) reversed outright once fixed, and
[repair-vs-rewrite](../04_repair_vs_rewrite) gained 9 fixes in its repair arm. Finding a bug
in three projects and having one of them survive re-measurement is a better outcome than all
three surviving would have been &mdash; it means the check had teeth.

A second project agrees from the other direction:
[repair vs rewrite](../04_repair_vs_rewrite) finds **77.0%** of first-attempt failures
survive *both* a repair and a from-scratch rewrite.

## Running it

```bash
python run.py --limit 500 --rounds 5
```

## Limits

- The curve cannot show a fix that passes the tests and is still wrong. Feedback-driven
  repair optimises for the tests it is shown &mdash; see
  [mbpp-false-accepts](https://github.com/hammasbuilds/mbpp-false-accepts), where MBPP's
  three asserts accept 17.6% of provably wrong programs.
- MBPP tasks are short and single-function. Where a first attempt lands closer to right, or
  the traceback carries more than one frame, later rounds may pay.
- Each round is a fresh seed, so a task solved in round 2 is not necessarily "learning from
  the error" rather than a second sample. Separating those needs a no-feedback resample arm,
  which [feedback-content](../13_feedback_content) provides at one round: retrying with no
  feedback at all fixes 8.4%, against 18.3% when shown the failing assert and its value.
