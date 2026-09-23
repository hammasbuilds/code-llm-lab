<h1 align="center">coder-vs-generalist</h1>
<p align="center"><i>Is a code-tuned model worth it, and does the advantage shrink with size?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-500-blue" alt="">
  <img src="https://img.shields.io/badge/advantage%2520at%25203B-%252B11.4pp-2ea44f" alt="">
  <img src="https://img.shields.io/badge/advantage%2520at%252014B-%252B10.0pp-2ea44f" alt="">
  <img src="https://img.shields.io/badge/direction-shrinks-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Five models, same 500 tasks, same prompt. Two matched pairs &mdash; a coder model and its
general-purpose sibling at the same size, same family, same quantisation &mdash; so the
comparison is about the tuning and not about the parameter count.

## Result

```
qwen2.5-coder:14b     14B coder     76.6%
qwen2.5:14b-instruct  14B general   66.6%     coder advantage at 14B: +10.0pp
qwen2.5-coder:3b       3B coder     60.6%
qwen2.5:3b-instruct    3B general   49.2%     coder advantage at  3B: +11.4pp
llama3.2:3b            3B general   40.4%
```

**The code-tuned model wins at both sizes, and the advantage shrinks with scale** &mdash;
+11.4 points at 3B, +10.0 at 14B.

That is the hypothesis this project was written to test: a bigger general model has already
learned most of what the specialisation buys, so **a second set of weights in VRAM is hardest
to justify exactly where those weights cost the most.**

**The 3B coder beats the 3B generalist by more than `llama3.2:3b` trails either of them**,
which is the practical version: at small sizes, tuning is worth more than switching families.

The two-directional reading, which a one-way count would overstate:

```
14B: 69 tasks only the coder solves, 19 only the generalist does
     net +50, not +69 - overstated by 19
 3B: 84 tasks only the coder solves, 27 only the generalist does
     net +57, not +84 - overstated by 27
```

Roughly one task in four that the coder "wins" is paid for by one it loses. A model swap is
a trade, not an upgrade, and the headline difference hides both halves.

### This reverses what the 250-task run reported

At 250 tasks this page said the advantage **grew** with scale &mdash; +8.8pp at 3B, +11.2pp
at 14B &mdash; and made a point of the fact that it "refutes the hypothesis this project was
written to test", noting that the branch predicting a shrinking gap never fired.

At 500 tasks it fires:

| | 3B | 14B | direction |
|---|---:|---:|---|
| 250 tasks | +8.8 | +11.2 | grows |
| **500 tasks** | **+11.4** | **+10.0** | **shrinks** |

Every individual score moved by under two points; what flipped is a **difference of
differences**, which is the most fragile quantity on the page and the one a doubled sample
was most likely to overturn. The earlier limits section said as much &mdash; *"two sizes is
two points; 'grows with scale' is the direction between them, not a curve"* &mdash; but the
headline asserted the direction anyway.

The honest reading now: **the advantage is real and roughly 10&ndash;11 points at both
sizes, and this design cannot reliably resolve which end is larger.** A 1.4-point gap between
two gaps, each measured on 500 tasks, is not something two points on a curve can settle.
Treat "shrinks" as the better-supported direction, not an established one.

## Running it

```bash
python run.py --limit 500
```

Needs Ollama with all five models pulled.

## Limits

- **Two sizes is two points.** The direction between them is not a curve, and it already
  changed sign once when the sample doubled. Three sizes would be the minimum to claim a
  trend; this cannot.
- One family plus one outsider. Whether it holds for other families is untested.
- Runs on the first 500 MBPP tasks, which is mostly its held-out test split
  (ids 11&ndash;510) &mdash; so this is the least contamination-affected table in the repo.
  See the [note in the root README](../../README.md#a-caveat-that-applies-to-every-mbpp-row-below).
- One sample at temperature 0 per model. [determinism](../18_determinism) shows 0.8% of
  tasks flip verdict between identical runs, which is small against a 10-point gap but not
  against the 1.4-point difference between the two gaps.
