<h1 align="center">context-dilution</h1>
<p align="center"><i>Bury the real task in unrelated examples. When does it start to hurt?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-972-blue" alt="">
  <img src="https://img.shields.io/badge/k-0%2520to%252024-blue" alt="">
  <img src="https://img.shields.io/badge/aggregate%2520cost-0.9pp-64748b" alt="">
  <img src="https://img.shields.io/badge/churn-9.8%25-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Prompt the model with *k* unrelated solved MBPP tasks before the one it has to solve.
The task is identical in every arm; only the surrounding context grows.

## Result

All 972 MBPP tasks, with k irrelevant solved tasks pasted in ahead of the real one.

```
k= 0   80.3%
k= 2   78.5%
k= 8   79.0%
k=24   79.4%

pass@1 change, k=0 -> k=24 : -0.9%
prompt grew                : 15.7x
```

**Sixteen times the prompt, none of it relevant, costs 0.9 points.** There is no dilution
curve at this scale - the k=2 arm is the *worst* of the four, and k=24 is better than k=2.
Reported as a non-result rather than dressed up as a trend.

But the aggregate is hiding the interesting number:

```
solved at k=0, lost by k=24   : 52  (5.3%)
failed at k=0, gained by k=24 : 43  (4.4%)
churn, either direction       : 95  (9.8%)
```

**Nearly one task in ten changes verdict**, and the headline is flat because the losses and
the gains are almost equal. That is not the same as the extra context being harmless. Fifty-
two tasks that worked without the padding stopped working with it; forty-three did the
reverse, for reasons that have nothing to do with the tasks themselves.

The practical consequence is for retrieval. A retriever that fetches k passages pays this on
every one it gets wrong - not as a visible drop in the average, but as churn underneath it.
If you measure a RAG change by its aggregate score, a system that silently swapped which 5%
of queries it answers correctly will look like no change at all.

This is the third project here to land on the same shape: a stable aggregate over unstable
per-task behaviour. [prompt-shape-variance](../05_prompt_shape_variance) finds 22.4% flipping
on wording alone, and [determinism](../18_determinism) finds 0.8% flipping on nothing at all.

## Running it

```bash
python run.py --limit 972
```

## Limits

- Distractors are other MBPP tasks: same domain, same format, same length. Adversarial or
  off-domain filler is a different question.
- One model. A 3B has less room and would be the interesting comparison.
