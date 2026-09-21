<h1 align="center">review-false-alarms</h1>
<p align="center"><i>Ask a model to review correct code. How often does it invent a bug?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-972-blue" alt="">
  <img src="https://img.shields.io/badge/recall%2520on%2520buggy-45.5%25-b8860b" alt="">
  <img src="https://img.shields.io/badge/false%2520alarms%2520on%2520reference-37.3%25-b91c1c" alt="">
  <img src="https://img.shields.io/badge/precision-34.0%25-b91c1c" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Three arms, one prompt: *review this function and say whether it has a bug.*

- **buggy** - code the model wrote that fails MBPP's tests
- **passing** - code the model wrote that passes them
- **reference** - MBPP's own reference solution, correct by definition

The third arm is the one that matters. Anything flagged there is a false alarm with no
argument available.

## Result

```
                  flagged      rate
buggy            87/191      45.5%   <- what it catches
passing         169/781      21.6%
reference       363/972      37.3%   <- every one of these is wrong
```

**It flags the reference solution almost as often as it flags real bugs** - 37.3% against
45.5%. Precision across the run is **34.0%**: two thirds of what it raises is noise.

A reviewer that catches four or five bugs in ten and invents four in ten is not a filter. As
a gate it would reject over a third of correct code; as advice it teaches people to ignore
it.

The gap between `passing` (21.6%) and `reference` (37.3%) is the sharper result, and four
times the data did not soften it. Both arms are correct code. The difference is that one is
the model's *own* output and the other is somebody else's style &mdash; **unfamiliar style
reads as suspicious, at 1.7&times; the rate.** A review tool applied to a codebase it did not
write inherits that multiplier.

Every number moved by under three points from the 250-task run, and precision fell from
44.8% to 34.0%, entirely because the larger corpus has a lower share of buggy code to find.
Nothing about the behaviour changed; the small run just had a friendlier denominator.

## Running it

```bash
python run.py --limit 972
```

## Limits

- One review prompt. A different phrasing would move the flag rate, which is the point
  [prompt-shape-variance](../05_prompt_shape_variance) makes.
- "Has a bug" is a blunt question. A reviewer asked for specific classes of defect might
  behave very differently.
- 20 responses across the three arms could not be parsed into a verdict and are excluded
  from the rates rather than counted as either answer.
- The `buggy` arm is buggy *by MBPP's three asserts*, which
  [mbpp-false-accepts](https://github.com/hammasbuilds/mbpp-false-accepts) shows accept
  17.6% of provably wrong programs. Some of the `passing` arm is wrong code the benchmark
  did not catch, which makes the false-alarm rate on that arm a mild overestimate.
