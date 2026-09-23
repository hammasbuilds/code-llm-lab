<h1 align="center">batch-vs-single</h1>
<p align="center"><i>Ask for eight solutions in one response. What does batching cost?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-968-blue" alt="">
  <img src="https://img.shields.io/badge/drop%2520at%2520batch%25208-4.5pp-b91c1c" alt="">
  <img src="https://img.shields.io/badge/not%2520emitted-2%2520of%2520968-2ea44f" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---


Batching tasks into one request is the obvious way to cut cost. This measures what it
costs in return: solve the same 160 tasks one per request, then two, four and eight per
request, and score them identically.

## Result

968 tasks (trimmed to a multiple of 8 so every batch size sees identical work).

```
batch=1   79.1%
batch=2   77.9%   -1.2
batch=4   76.2%   -2.9
batch=8   74.6%   -4.5

functions never emitted at all : 2 of 968
```

**Asking for eight functions at once costs 4.5 points**, and the cost is monotonic in batch
size - unlike [context-dilution](../10_context_dilution), where a 16x longer prompt produced
no curve at all. Length is not what hurts here; being one of several answers is.

### Position matters, but not by as much as the raw numbers say

```
slot   1      2      3      4      5      6      7      8
     73.6%  75.2%  72.7%  70.2%  78.5%  72.7%  67.8%  86.0%
```

Read directly, that says the last slot beats the first by 12.4 points - and beats asking for
the function *on its own* (79.1%), which is impossible. **Each slot holds a different 121
tasks**, so position is confounded with task difficulty. Against each slot's own single-task
baseline:

| slot | batch=8 | batch=1, same tasks | real effect |
|---|---:|---:|---:|
| 1 | 73.6% | 78.5% | **-4.9** |
| 4 | 70.2% | 76.0% | -5.8 |
| 7 | 67.8% | 76.0% | **-8.2** |
| 8 | 86.0% | 83.5% | **+2.5** |

Slot 8's tasks were already the easiest in the set. The honest finding is smaller and
different from the raw table: **every position degrades except the last**, the worst is the
*second to last* rather than the first, and the first-to-last difference is about 7 points
of effect rather than 12.4 of score.

### The parser was the previous finding

This project used to report a **9.4-point** cost and **"8 of 160 solutions never emitted at
all"**. `split_functions` called `ast.parse` on the whole batch response and returned nothing
on `SyntaxError`, so **one unmatched bracket discarded all eight functions in that batch**.
It happened in 1 of 20 batches, and those eight were the entire "never emitted" claim - a
statement about the model that was a statement about one stray `)` on line 2.

Re-scored on the same responses with each `def` block parsed on its own, sizes 1, 2 and 4 did
not move at all and size 8 recovered 7 of the 8. That the unaffected sizes stayed still is
what shows the fix repaired one case rather than inflating everything.

## Running it

```bash
python run.py --limit 972
```

## Limits

- One model and one prompt format. A batching format designed for the job - numbered slots,
  a schema - would likely lose less.
- Cost is not measured here, only accuracy. Batch 8 is far cheaper per task; whether 9.4
  points is worth it is a decision this does not make.
