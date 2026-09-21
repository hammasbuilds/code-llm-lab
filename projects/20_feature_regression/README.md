<h1 align="center">feature-regression</h1>
<p align="center"><i>Add a feature to working code. How often does the old behaviour break?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/eligible-190-blue" alt="">
  <img src="https://img.shields.io/badge/worst%2520change-11.1%25-b91c1c" alt="">
  <img src="https://img.shields.io/badge/regressed%2520under%2520any-29-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Take solutions the model got right, ask for one additive change, and re-run the
original tests. The change is always meant to *extend* the function, never to alter what it
already does - so every failure is a regression the request did not ask for.

This is [refactor-safety](../11_refactor_safety) from the other side: that one forbids
behaviour change, this one is silent about it and adds work.

## Result

```
change        regressed
validate        11.1%     add argument validation
generalise       4.2%     make it work for one more input type
default          1.1%     add an optional parameter
logging          0.0%     add a log line
```

**`validate` is the dangerous one, and the reason is in its name.** Asked to reject bad
input, the model adds a guard that also rejects input the original accepted - 21 of 190
solutions, every one an `error` rather than a wrong answer, so the new check is firing on
cases the tests already covered.

**`logging` never broke anything**, which is the expected result and worth having stated:
adding a side effect that does not touch the return path is safe 190 times out of 190.

29 of 190 solutions regressed under at least one change; **0 regressed under all four**. As
in refactor-safety, the risk is not that certain code is fragile - it is that each kind of
change has its own way of going wrong.

## Running it

```bash
python run.py --limit 250
```

## Limits

- "Regressed" means MBPP's tests fail. A change that alters untested behaviour is invisible,
  and MBPP's tests are three asserts.
- Four change types, all additive and all small. A feature request that genuinely requires
  restructuring is a different question.
