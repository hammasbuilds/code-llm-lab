<h1 align="center">feature-regression</h1>
<p align="center"><i>Add a feature to working code. How often does the old behaviour break?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/eligible-781-blue" alt="">
  <img src="https://img.shields.io/badge/worst%2520change-10.4%25-b91c1c" alt="">
  <img src="https://img.shields.io/badge/logging-0%2F781-2ea44f" alt="">
  <img src="https://img.shields.io/badge/regressed%2520under%2520any-105-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Take the 781 solutions the model got right across all 972 MBPP tasks, ask for one additive
change, and re-run the original tests. The change is always meant to *extend* the function,
never to alter what it already does &mdash; so every failure is a regression the request did
not ask for.

This is [refactor-safety](../11_refactor_safety) from the other side: that one forbids
behaviour change, this one is silent about it and adds work.

## Result

```
change        regressed        how it broke
validate      81/781  10.4%    80 error, 1 wrong answer     add argument validation
generalise    27/781   3.5%    24 error, 3 wrong answers    make it work for one more input type
default        3/781   0.4%     2 error, 1 wrong answer     add an optional parameter
logging        0/781   0.0%     -                           add a log line
```

**`validate` is the dangerous one, and the reason is in its name.** Asked to reject bad
input, the model adds a guard that also rejects input the original accepted. 80 of its 81
failures are an `error` rather than a wrong answer, so the new check is firing on cases the
original tests already covered &mdash; it is not computing the wrong thing, it is refusing to
compute at all.

**`logging` never broke anything, 0 out of 781.** At 190 that was a plausible zero; at 781 it
is a real one. Adding a side effect that does not touch the return path is safe.

### The `default` arm is the control, and it is not quite zero

Adding an optional parameter with a default **cannot break a caller by construction** &mdash;
the old signature and the old behaviour both remain valid. So the floor for that arm is 0,
and it came in at 3.

Those 3 are not the feature. They are the model rewriting something it was asked to leave
alone, on a change that gave it no reason to. That puts a number on the background rate of
gratuitous edits: **0.4%**, which is the amount of `validate`'s 10.4% that has nothing to do
with validation. It is small, and knowing it is small is what lets the other three arms be
read at face value.

105 of 781 solutions regressed under at least one change; **0 regressed under all four**. As
in refactor-safety, the risk is not that certain code is fragile &mdash; it is that each kind
of change has its own way of going wrong.

Every rate came down slightly from the 190-task run (validate 11.1% &rarr; 10.4%, generalise
4.2% &rarr; 3.5%, default 1.1% &rarr; 0.4%) and the ordering did not change.

## Running it

```bash
python run.py --limit 972
```

## Limits

- "Regressed" means MBPP's tests fail. A change that alters untested behaviour is invisible,
  and MBPP's tests are three asserts &mdash; which
  [mbpp-false-accepts](https://github.com/hammasbuilds/mbpp-false-accepts) shows accept
  17.6% of provably wrong programs. **Every rate here is a lower bound.**
- The eligible 781 are the tasks this model already solves, so they skew easy, and they skew
  toward MBPP's training split (see the contamination note in the
  [root README](../../README.md#a-caveat-that-applies-to-every-mbpp-row-below)). This
  measures regressions on code the model finds comfortable.
- Four change types, all additive and all small. A feature request that genuinely requires
  restructuring is a different question.
- One model, temperature 0, one attempt per change.
