<h1 align="center">confidence-gating</h1>
<p align="center"><i>Ask the model how sure it is. Can you act on the answer?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-250-blue" alt="">
  <img src="https://img.shields.io/badge/separation-0.06pp-b91c1c" alt="">
  <img src="https://img.shields.io/badge/distinct%2520values-2-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Every proposal to ship model-written code safely rests on the model knowing when it is
guessing. So: ask for an answer and a confidence score, then check whether the score
separates right answers from wrong ones.

## Result

```
mean confidence when CORRECT : 99.97
mean confidence when WRONG   : 99.92
separation                   :  0.06 percentage points

distinct confidence values it ever emitted: {95, 100}
```

**The model reports 100 for nearly everything, including the answers that fail.** Across 249
tasks that stated a confidence, the score took two distinct values in total.

A gate needs a threshold and there is nowhere to put one. Every cutoff from 0 to 100 leaves
precision at **75.5%** with **100% coverage** - identical to not gating at all. The number is
emitted, formatted and parsed correctly, and it carries no information.

Worth stating plainly, because the failure is invisible from the output: the response looks
like calibrated self-assessment. It is a constant.

## Running it

```bash
python run.py --limit 250
```

## Limits

- Verbalised confidence only. Token log-probabilities are a different signal and might
  separate where this does not; Ollama's API does not expose them here.
- One model at temperature 0. Sampling repeatedly and measuring agreement is the other
  standard approach - [temperature-pass-at-k](../06_temperature_pass_at_k) touches it.
