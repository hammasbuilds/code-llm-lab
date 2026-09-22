<h1 align="center">prompt-shape-variance</h1>
<p align="center"><i>How much of a benchmark score is the wording?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-972-blue" alt="">
  <img src="https://img.shields.io/badge/shapes-5-0f766e" alt="">
  <img src="https://img.shields.io/badge/spread-2.1%2520pts-64748b" alt="">
  <img src="https://img.shields.io/badge/flipped-22.4%25-b45309" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Five phrasings carrying identical information. Same model, same temperature, same
tasks, same execution rule &mdash; the only variable is how the task is written.

## Result

All 972 MBPP tasks, each asked five ways.

```
plain       80.6%
comment     80.1%
signature   79.8%
terse       79.2%
docstring   78.5%

spread      2.1%   attributable to formatting alone
stdev       0.7%
```

**The aggregate barely moves.** Two points between the best and worst phrasing, and a
standard deviation under one point. If you only ever looked at the score, you would conclude
that prompt shape does not matter here.

Now look underneath it:

```
solved by at least one phrasing : 860  (88.5%)
solved by every phrasing        : 642  (66.0%)
flipped on phrasing alone       : 218  (22.4%)
```

**218 tasks are solved under one wording and failed under another** &mdash; while the scores
those wordings produce sit within two points of each other. For those 218 the benchmark is
not measuring whether the model can write the function. It is measuring which sentence it
was handed.

The two numbers together are the finding. **A stable aggregate is not evidence of stable
behaviour.** The phrasings agree on the total almost exactly *because* the tasks each one
wins and loses cancel out, not because they are solving the same tasks.

There is also 8 points of headroom nobody collects: the best single phrasing reaches 80.6%,
but 88.5% of tasks are solvable by *some* phrasing.

### What the 200-task run got wrong, and what it got right

| | 200 tasks | 972 tasks |
|---|---:|---:|
| spread | **7.5 pts** | **2.1 pts** |
| flip rate | 24.0% | **22.4%** |

The spread was noise and it averaged away, almost exactly as the earlier write-up warned it
might &mdash; it called 7.5 points "worth knowing" and then argued the flip rate mattered
more. At five times the data the flip rate held within 1.6 points and the spread lost two
thirds of its size.

So the original conclusion survives in a stronger form than it was stated. It hedged that
"two papers reporting 74% and 78% may not disagree about the model at all". The honest
version is sharper: **five phrasings reporting 78.5% to 80.6% do not disagree about the
score either, and still disagree about 218 individual tasks.**

This is the **input** half of a pair.
[code-eval-harness](https://github.com/hammasbuilds/code-eval-harness) measured the output
half: identical generations scoring 0% or 94% depending only on the extraction rule.

## Running it

```bash
python run.py --limit 972
```

## Limits

- Five shapes, hand-written. A different five would give a different spread; the flip rate
  is the more robust quantity, and it is the one that held up across a 5&times; increase in
  sample size.
- Temperature 0 throughout, so none of this spread is sampling noise. It is also not
  separated from it: a task that flips between phrasings might also flip between seeds of
  the *same* phrasing, which is not measured here and would need a same-prompt resample arm
  to rule out.
- Runs on all 972 MBPP tasks, which includes its training split &mdash; see the
  [contamination note](../../README.md#a-caveat-that-applies-to-every-mbpp-row-below). The
  flip rate is a within-task comparison, so contamination affects the level of every arm
  equally and not the difference between them.
