<h1 align="center">repair-vs-rewrite</h1>
<p align="center"><i>Patch the failure, or throw it away and start over?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-972-blue" alt="">
  <img src="https://img.shields.io/badge/failures-191-ef6461" alt="">
  <img src="https://img.shields.io/badge/survived%20both-77.0%25-red" alt="">
  <img src="https://img.shields.io/badge/repair%20vs%20rewrite-p%3D0.43-64748b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Agents almost always patch. The alternative &mdash; discard it and regenerate from the
task &mdash; is rarely tried and almost never compared, even though the two have different
costs. Repair sends the broken code *and the error* back in the prompt, so it costs more
tokens **and** anchors the model on an approach that already failed.

Both arms start from the same failed first attempt and get exactly one more call, so the
comparison is paired across all 191 failures.

## Result

```
first attempt pass@1 : 80.3%   (191 failures to work with)

repair  fixed :  27  (14.1%)
rewrite fixed :  21  (11.0%)
both          :   4
neither       : 147  (77.0%)
```

**Most failures survive both.** 77.0% are fixed by neither strategy.

This project still does **not** report "repair beats rewrite". Paired, it is 23 tasks repair
fixed alone against 17 rewrite fixed alone, an exact McNemar **p = 0.43**. The two are not
distinguishable, and the 3.1-point gap is the kind of number that looks like a result and
is not.

### The two fix almost disjoint sets

```
repair only   23
rewrite only  17
both           4      <- only 4 of 44
either        44  (23.0%)
```

Either strategy alone recovers about an eighth of the failures; running both recovers
**23.0%**, because they so rarely succeed on the same task. That is the useful finding, and
it is the opposite of the question everyone asks &mdash; the choice between them matters far
less than the decision to do both.

## The error message was worth measuring, and it had never been sent

Until this run the repair arm was handed the string `AssertionError` and nothing else.
`Outcome.detail` is stderr's **last line**, which for an assertion failure is exactly that
one word &mdash; no file, no line, no source, no values. So the "repair" prompt read:

```
Running the tests gave:
AssertionError
```

That handicaps exactly one side. **Rewrite never reads an error message**, so a broken error
message could only ever hurt repair &mdash; and a rigged comparison that concludes "repair is
no better than starting over" is the result the bug was always going to produce.

Re-run with a real traceback, paired on the same 191 failures:

```
repair    18 -> 27    gained 12, lost 3    p = 0.035
rewrite   21 -> 21    the identical 21 tasks, one for one
```

**Rewrite did not move by a single task.** That is the control: the only arm that reads the
error message is the only arm that changed, exactly as it should, which is what makes the
+9 on repair worth believing rather than run-to-run drift.

So the error message is worth roughly **9 failures in 191** to a repair loop &mdash; and the
previous version of this README, reporting repair at 9.4%, was quoting a number produced by
feeding a model one word. It said "the two are indistinguishable (p=0.72)". The conclusion
survives at p=0.43; the reasoning behind it did not.

[feedback-content](../13_feedback_content) reaches the same place from the other direction,
with the same bug found in its own `traceback` arm: a real traceback takes a retry from 8.4%
to 14.1%, and a length-matched control with no information scores *below* the baseline.

## What this means for the self-debug ceiling

[self-debug-ceiling](../02_self_debug_ceiling) says retry loops plateau after two rounds. It
had the same bug &mdash; every round was shown `AssertionError` &mdash; and is being
re-measured. Until it lands, treat "retry strategies are a rounding error on MBPP" as
unproven: 77.0% of failures here survive everything, but 23.0% do not, and that is no longer
a rounding error.

## Running it

```bash
python run.py --limit 972
```

## Limits

- One retry each, one model, temperature 0.
- The two arms use different seeds (1 and 2), so part of the disjointness is ordinary
  sampling variance rather than a property of the strategies. A same-seed rewrite arm would
  separate those and is not run here.
- 191 failures supports the 77.0% comfortably and is still too small to detect a difference
  between the arms smaller than roughly 8 points.
- The traceback comes from MBPP-shaped programs: one short function, a literal assert. A
  failure deep inside a larger program carries much more, so the +9 is a floor for what a
  real error message is worth, not a ceiling.
