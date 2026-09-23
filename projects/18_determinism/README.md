<h1 align="center">determinism</h1>
<p align="center"><i>Temperature 0 is not the same as deterministic. How much does it move?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-400-blue" alt="">
  <img src="https://img.shields.io/badge/runs-5-blue" alt="">
  <img src="https://img.shields.io/badge/pass@1%2520spread-0.8pp-2ea44f" alt="">
  <img src="https://img.shields.io/badge/verdicts%2520that%2520flipped-3-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Everything in this repo that does not vary temperature runs at 0, on the usual
understanding that greedy decoding makes a run reproducible. Published evaluations lean on
the same assumption: a pass@1 at temperature 0 is reported as a fact about the model, not as
one draw.

It is not quite true. Greedy decoding picks the highest-probability token, but those
probabilities come out of floating-point arithmetic whose order is not fixed - batching,
kernel selection and GPU reduction order all move the last bits. Where two tokens are close,
that is enough to change which one wins, and the rest of the sequence follows.

**The generation cache is bypassed for this project.** With it on, every run after the first
would be a copy by construction, and the answer would be 100% determinism by definition.

## Result

400 tasks, the same prompt sent five times, temperature 0 throughout.

```
identical prompt gave different TEXT     : 28/400  (7.0%)
identical prompt gave a different VERDICT:  3/400  (0.8%)
mean distinct outputs per task           : 1.07 of 5

pass@1 across the five runs : 75.2% - 76.0%
mean                        : 75.8%
stdev                       : 0.29%
```

**The score is stable. The tasks are not.**

Five runs land within eight tenths of a point of each other, a standard deviation under a
third. Quote any one of them and you have quoted them all. Yet **three tasks flip between
pass and fail with nothing changed at all** - same prompt, same model, same temperature, same
machine - and 28 return text that differs somewhere.

The score is stable *because the flips cancel*, not because the decoding is deterministic.
A single evaluation run is one draw from this distribution, not a measurement of the model.

```
distinct outputs per task
  1 distinct : 372 tasks
  2 distinct :  27 tasks
  3 distinct :   1 task
```

This is the same shape as [prompt-shape-variance](../05_prompt_shape_variance), reached from
the opposite end. That project varies the wording and holds everything else; this one varies
**nothing** and still moves. Between them: a benchmark score can be reproducible to a tenth
of a point and still not be measuring a stable property of the model.

At 120 tasks this project reported five identical pass@1 figures and a 1.7% flip rate. At 400
the figures are no longer identical - a 0.8-point spread appears - and the flip rate falls to
0.8%. Both moved toward the middle, which is what a small sample usually hides in both
directions at once.

## Running it

```bash
python run.py --limit 400 --runs 5
```

Takes real GPU time - there is no cache to fall back on, by design.

## Limits

- One model, one backend, one machine. Determinism is a property of the whole stack: another
  GPU, another batch size or another Ollama build would give a different number.
- Five runs. A 1.7% flip rate measured over 600 generations has a wide interval around it, and
  the two flipping tasks are two tasks.
- Text variation is compared exactly. A response differing only in whitespace counts as
  different, which is the strict reading; the verdict number is the one that matters.
