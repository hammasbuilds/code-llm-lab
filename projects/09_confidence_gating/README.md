<h1 align="center">confidence-gating</h1>
<p align="center"><i>Can you auto-merge on the model's own confidence?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-972-blue" alt="">
  <img src="https://img.shields.io/badge/says%2520100-99.0%25-b91c1c" alt="">
  <img src="https://img.shields.io/badge/separation-%2B0.1%2520pts-b91c1c" alt="">
  <img src="https://img.shields.io/badge/best%2520gate-%2B0.2%2520pts-64748b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

The pitch for a self-reported confidence score is that it lets you gate: merge the
high-confidence answers automatically, send the rest to a human. For that to work the score
has to **discriminate** &mdash; it must be higher on solutions that pass than on ones that
fail. Whether it does is measurable, and it is not measured nearly often enough.

Ask for a solution and a confidence together, on all 972 MBPP tasks.

## Result

The model answers the question almost every time. The answer is always the same.

```
confidence   85 :    1   ( 0.1%)
confidence   95 :    4   ( 0.4%)
confidence  100 :  962   (99.0%)
no answer       :    5   ( 0.5%)
```

**It says 100 for 99% of tasks, including the 191 it gets wrong.**

```
mean confidence when correct : 100.0   (n=776)
mean confidence when wrong   :  99.9   (n=191)
separation                   :  +0.1 points
```

A score that moves by a tenth of a point between right and wrong answers carries no
information about which is which. And the consequence is not that gating works badly &mdash;
it is that gating does not exist:

```
threshold  merged  coverage  precision   vs base
        0     967    100.0%      80.2%       +0.0%
       50     967    100.0%      80.2%       +0.0%
       70     967    100.0%      80.2%       +0.0%
       80     967    100.0%      80.2%       +0.0%
       90     966     99.9%      80.3%       +0.1%
      100     962     99.5%      80.4%       +0.2%
```

**Every threshold from 0 to 80 is identical to not gating at all**, because nothing scores
below 85. The strictest possible gate &mdash; demand a perfect 100 &mdash; still
auto-merges **99.5%** of tasks and buys 0.2 points of precision. There is no operating
point. The dial is not connected to anything.

Four times the data sharpened this rather than softening it: at 250 tasks the model used
2 distinct values, at 972 it uses 3, and the separation went from 0.06 to 0.09 points.

### What was checked before believing it

A distribution this degenerate is usually a parsing bug, so:

- **The parser takes the *last* `CONFIDENCE:` match**, not the first, so a model restating
  the instruction before answering cannot have its own echo scored. Already correct.
- **The model writes the confidence line *inside* the code fence**, so it lands in the
  executed candidate in 262 of 263 responses. It survives only because `CONFIDENCE: 100`
  is a valid bare annotation in Python. `CONFIDENCE: 95%` and `**CONFIDENCE: 95**` are
  `SyntaxError`, and the parser reads a number out of both &mdash; so a change in
  formatting would record a confidence while scoring the code it describes as broken. Now
  stripped; verified to leave every verdict identical.
- **264 of 265 submissions contain asserts the model wrote itself.** Stripping them flips
  nothing: it copies MBPP's own test out of the prompt, so its self-tests carry no
  information the real tests do not. That is the failure that cost
  [test-first](../17_test_first) 54 points, and it is not present here.

The finding is the model's behaviour, not the harness's.

## Running it

```bash
python run.py --limit 972
```

## Limits

- One phrasing of the request. A calibration prompt that asks for a probability, or offers
  a rubric, might get a distribution with some spread &mdash; this measures the naive ask,
  which is also the one most people actually make.
- Temperature 0, one sample. Sampling several times and using agreement as the confidence
  signal is a different and probably better idea, and is not tested here.
- One model. A larger or RLHF-tuned model may be better calibrated; nothing here says it is
  not.
