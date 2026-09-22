<h1 align="center">batch-vs-single</h1>
<p align="center"><i>Ask for eight solutions in one response. What does batching cost?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-160-blue" alt="">
  <img src="https://img.shields.io/badge/drop%2520at%2520batch%25208-9.4pp-b91c1c" alt="">
  <img src="https://img.shields.io/badge/not%2520emitted-8-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

> ### &#9888; These numbers are being re-measured
>
> `split_functions` called `ast.parse` on the whole batch response and returned nothing on
> `SyntaxError`, so **one unmatched bracket discarded all eight functions in that batch**.
> It happened in 1 of 20 batches at size 8, and those eight are the entirety of the
> "8 of 160 solutions were never emitted at all" claim below - a statement about the model
> that was a statement about one stray `)` on line 2 of one response.
>
> Re-scored on the *same* cached responses, with each `def` block parsed on its own:
>
> | batch size | pass, before | pass, after | never emitted, before | after |
> |---:|---:|---:|---:|---:|
> | 1 | 121/160 | 121/160 | 0 | 0 |
> | 2 | 116/160 | 116/160 | 0 | 0 |
> | 4 | 113/160 | 113/160 | 0 | 0 |
> | **8** | 106/160 | **111/160** | **8** | **1** |
>
> So the cost of batching eight is **6.2 points, not 9.4** - a third of the reported figure
> was the parser - and exactly **one** function was genuinely missing. Sizes 1, 2 and 4 are
> untouched, which is the check that the fix is not simply inflating everything.
>
> The full re-run is queued at 972 tasks and will replace the tables below.

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
