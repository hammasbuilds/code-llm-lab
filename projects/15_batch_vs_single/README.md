<h1 align="center">batch-vs-single</h1>
<p align="center"><i>Ask for eight solutions in one response. What does batching cost?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-160-blue" alt="">
  <img src="https://img.shields.io/badge/drop%2520at%2520batch%25208-9.4pp-b91c1c" alt="">
  <img src="https://img.shields.io/badge/not%2520emitted-8-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Batching tasks into one request is the obvious way to cut cost. This measures what it
costs in return: solve the same 160 tasks one per request, then two, four and eight per
request, and score them identically.

## Result

```
batch   pass@1    not emitted
1       75.6%          0
2       72.5%          0
4       70.6%          0
8       66.3%          8
```

**Monotonic, and it costs 9.4 points by batch 8.** Unlike
[context-dilution](../10_context_dilution), where no trend appeared, this one is a real
ordering: every increase in batch size loses accuracy.

**Eight tasks also means eight answers, and at batch 8 the model simply stopped emitting
some** - 8 of 160 solutions never appeared in the response at all. Those are scored as
failures, because a solution you did not get is not a solution.

The by-position numbers say the loss is not "it gets tired at the end":

```
batch 8, by position:  75%  60%  70%  60%  55%  65%  70%  75%
```

The *middle* is worst. First and last positions score 75%; position 4 scores 55%. That is a
primacy-and-recency shape, not a truncation.

## Running it

```bash
python run.py --limit 160
```

## Limits

- One model and one prompt format. A batching format designed for the job - numbered slots,
  a schema - would likely lose less.
- Cost is not measured here, only accuracy. Batch 8 is far cheaper per task; whether 9.4
  points is worth it is a decision this does not make.
