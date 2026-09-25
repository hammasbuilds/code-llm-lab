<h1 align="center">determinism</h1>
<p align="center"><i>Temperature 0 is not the same as deterministic. How much does it move?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-400-blue" alt="">
  <img src="https://img.shields.io/badge/runs-8-blue" alt="">
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

400 tasks, the same prompt sent **eight** times, temperature 0 throughout, cache off.

```
identical prompt gave different TEXT     : 31/400  (7.8%)
identical prompt gave a different VERDICT:  3/400  (0.8%)
mean distinct outputs per task           : 1.08 of 8

pass@1 per run : 75.2  76.0  76.0  75.8  76.0  76.0  75.8  76.0
spread         : 0.8 points
stdev          : 0.25%
```

**The score is stable. The tasks are not.**

Eight runs land within eight tenths of a point of each other. Quote any one of them and you
have quoted them all. Yet **three tasks flip between pass and fail with nothing changed at
all** - same prompt, same model, same temperature, same machine - and 31 return text that
differs somewhere.

The score is stable *because the flips cancel*, not because the decoding is deterministic.
A single evaluation run is one draw from this distribution, not a measurement of the model.

This replicates the five-run result almost exactly: 75.2-76.0% then, 0.8% flips then. Three
more seeds moved neither number.

### The first attempt at this reported 31.8%, and it was wrong

Worth recording, because the failure is invisible and the wrong number is far more
interesting than the right one.

The first eight-run attempt reported **127 of 400 tasks flipping verdict (31.8%)** and a
**31-point** pass@1 spread. Its per-run scores:

```
48.8   69.8   76.2   45.2   76.0   76.0   76.2   76.2
```

Five runs agree to within 0.2 points. Three are wrecked. Those three overlapped another
session loading a second 14B model onto the same 16 GB card - a trivial five-token request
to ollama was taking over ten seconds while both were resident. Requests timed out,
`generate()` returned `None`, the caller turned that into `""`, and an empty program fails
its tests **exactly like a wrong answer**.

The result was internally impossible and said so: 127 tasks flipped verdict while only 34
produced different text. A task whose output is byte-identical across runs cannot flip.

Two guards now, both in `run.py`:

- a run that loses more than 2% of its generations **raises** instead of returning a
  plausible list of empty strings
- progress prints with `flush=True`, because the old version buffered and a 75-minute run
  wrote nothing to its log - a stall and a healthy job looked identical

**Infrastructure failures must not be scoreable as model behaviour.** The same class of bug
had [code-eval-harness](https://github.com/hammasbuilds/code-eval-harness) write a results
file and exit 0 after losing all 492 of its generations.

## Running it

```bash
python run.py --limit 400 --runs 8
```

Takes real GPU time - there is no cache to fall back on, by design.

## Limits

- One model, one backend, one machine. Determinism is a property of the whole stack: another
  GPU, another batch size or another Ollama build would give a different number.
- Five runs. A 1.7% flip rate measured over 600 generations has a wide interval around it, and
  the two flipping tasks are two tasks.
- Text variation is compared exactly. A response differing only in whitespace counts as
  different, which is the strict reading; the verdict number is the one that matters.
