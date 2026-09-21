<h1 align="center">determinism</h1>
<p align="center"><i>Temperature 0 is not the same as deterministic. How much does it move?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-120-blue" alt="">
  <img src="https://img.shields.io/badge/runs-5-blue" alt="">
  <img src="https://img.shields.io/badge/pass@1%2520spread-0.0pp-2ea44f" alt="">
  <img src="https://img.shields.io/badge/verdicts%2520that%2520flipped-2-b8860b" alt="">
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

```
pass@1 per run : 81.7%  81.7%  81.7%  81.7%  81.7%
spread         :  0.0 percentage points

identical prompt gave different TEXT     : 11/120   (9.2%)
identical prompt gave a different VERDICT:  2/120   (1.7%)
mean distinct outputs per task           : 1.09 of 5
```

**Greedy decoding is not deterministic** - nearly one task in ten produced different text
across five identical requests, and two changed from passing to failing or back.

**And the aggregate did not move at all.** Five runs, five identical pass@1 figures, to the
decimal.

Those two statements sit together uncomfortably, and the second does not rescue the first.
A benchmark score being stable is not evidence that the thing underneath it is: here the
score is stable *because the flips cancelled*. For all five runs to land on exactly 98 of
120, exactly one of the two unstable tasks had to pass in every run - they took turns. Whether
that is coincidence or something structural is not decidable from five runs, and it is
reported rather than explained away.

## What to take from it

**For this repo:** the cache is not only a speed-up. It is what makes every other project
here reproducible, and the 1.7% verdict-flip rate is the size of the error it removes.

**For reading anyone's benchmark:** a difference of one or two points between two published
pass@1 numbers can be the same model twice. This run puts a floor under that - 1.7% of tasks
flipped verdict with *nothing* changed, which is about two points on a 120-task benchmark.

**The reassuring version is available and would be wrong:** "spread 0.0%, decoding is
deterministic" is true of the headline number and false of the thing it summarises.

## Running it

```bash
python run.py --limit 120 --runs 5
```

Takes real GPU time - there is no cache to fall back on, by design.

## Limits

- One model, one backend, one machine. Determinism is a property of the whole stack: another
  GPU, another batch size or another Ollama build would give a different number.
- Five runs. A 1.7% flip rate measured over 600 generations has a wide interval around it, and
  the two flipping tasks are two tasks.
- Text variation is compared exactly. A response differing only in whitespace counts as
  different, which is the strict reading; the verdict number is the one that matters.
