<h1 align="center">context-dilution</h1>
<p align="center"><i>Bury the real task in unrelated examples. When does it start to hurt?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-200-blue" alt="">
  <img src="https://img.shields.io/badge/k-0%2520to%252024-blue" alt="">
  <img src="https://img.shields.io/badge/worst%2520drop-3.5pp-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Prompt the model with *k* unrelated solved MBPP tasks before the one it has to solve.
The task is identical in every arm; only the surrounding context grows.

## Result

```
k=0     300 chars   77.0%
k=2     740 chars   74.5%
k=8    1895 chars   73.5%
k=24   4943 chars   76.5%
```

**There is no dilution curve.** A sixteen-fold increase in prompt length moves pass@1 by at
most 3.5 points, and the longest prompt beats two of the shorter ones. The ordering is not
monotonic, which is what a real effect would look like.

The honest reading is that the effect is not measurable at this scale - not that context is
free. 9 tasks are lost between k=0 and k=24 and 8 are gained: churn, not a trend.

**A longer context or a smaller model would likely show something.** 5,000 characters is
nowhere near this model's window, so the experiment as built never reaches the regime where
dilution is supposed to bite. That is a limit of the design, and it is the result.

## Running it

```bash
python run.py --limit 200
```

## Limits

- Distractors are other MBPP tasks: same domain, same format, same length. Adversarial or
  off-domain filler is a different question.
- One model. A 3B has less room and would be the interesting comparison.
