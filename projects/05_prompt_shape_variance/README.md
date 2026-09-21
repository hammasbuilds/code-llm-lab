<h1 align="center">prompt-shape-variance</h1>
<p align="center"><i>How much of a benchmark score is the wording?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-200-blue" alt="">
  <img src="https://img.shields.io/badge/shapes-5-0f766e" alt="">
  <img src="https://img.shields.io/badge/flipped-24%25-b45309" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Five phrasings carrying identical information. Same model, same temperature, same
tasks, same execution rule &mdash; the only variable is how the task is written.

## Result

```
plain       78.5%
docstring   75.5%
comment     74.5%
signature   74.5%
terse       71.0%

spread      7.5%   attributable to formatting alone
```

7.5% is worth knowing, but the sharper number is underneath it:

```
solved by at least one phrasing : 168  (84.0%)
solved by every phrasing        : 120  (60.0%)
flipped on phrasing alone       :  48  (24.0%)
```

**24.0% of tasks are solved under one wording and failed under
another.** For those 48 the benchmark is not measuring whether the model can
write the function. It is measuring which sentence it was handed.

The aggregate hides this completely. A 7.5% spread looks like noise you could
average away; a 24.0% flip rate means two papers reporting 74% and
78% here may not disagree about the model at all.

This is the **input** half of a pair.
[code-eval-harness](https://github.com/hammasbuilds/code-eval-harness) measured the output
half: identical generations scoring 0% or 94% depending only on the extraction rule.

## Running it

```bash
python run.py --limit 200
```

## Limits

- Five shapes, hand-written. A different five would give a different spread; the flip rate
  is the more robust quantity.
- Temperature 0 throughout, so none of this spread is sampling noise.
