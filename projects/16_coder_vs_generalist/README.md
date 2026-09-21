<h1 align="center">coder-vs-generalist</h1>
<p align="center"><i>Is a code-tuned model worth it, and does the advantage shrink with size?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-250-blue" alt="">
  <img src="https://img.shields.io/badge/advantage%2520at%252014B-%252B11.2pp-2ea44f" alt="">
  <img src="https://img.shields.io/badge/advantage%2520at%25203B-%252B8.8pp-2ea44f" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Five models, same 250 tasks, same prompt. Two matched pairs - a coder model and its
general-purpose sibling at the same size - so the comparison is about the tuning and not
about the parameter count.

## Result

```
qwen2.5-coder:14b        76.0%
qwen2.5:14b-instruct     64.8%     coder advantage at 14B: +11.2pp
qwen2.5-coder:3b         60.0%
qwen2.5:3b-instruct      51.2%     coder advantage at  3B:  +8.8pp
llama3.2:3b              41.6%
```

**The code-tuned model wins at both sizes, and the advantage grows with scale** - +8.8 points
at 3B, +11.2 at 14B.

That refutes the hypothesis this project was written to test. The expectation was that a
bigger general model would close the gap, because scale is supposed to subsume specialisation.
It does the opposite here, and the branch in the code that would have reported a shrinking
advantage never fired.

**The 3B coder beats the 3B generalist by more than llama3.2:3b trails either of them**, which
is the practical version: tuning is worth more than switching families at this size.

One number that needs the two-directional reading:

```
14B: 35 tasks only the coder solves, 7 only the generalist does
     net +28, not +35 - a one-way count overstates it by 7
 3B: 37 tasks only the coder solves, 15 only the generalist does
     net +22, not +37 - overstated by 15
```

## Running it

```bash
python run.py --limit 250
```

## Limits

- Two sizes is two points. "Grows with scale" is the direction between them, not a curve.
- One family plus one outsider. Whether this holds for other model families is untested.
