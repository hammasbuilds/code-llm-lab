<h1 align="center">review-false-alarms</h1>
<p align="center"><i>Ask a model to review correct code. How often does it invent a bug?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-250-blue" alt="">
  <img src="https://img.shields.io/badge/recall%2520on%2520buggy-43.3%25-b8860b" alt="">
  <img src="https://img.shields.io/badge/false%2520alarms%2520on%2520reference-38.8%25-b91c1c" alt="">
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
                 flagged     rate
buggy             26/60     43.3%   <- what it catches
passing           32/190    16.8%
reference         97/250    38.8%   <- every one of these is wrong
```

**It flags the reference solution almost as often as it flags real bugs** - 38.8% against
43.3%. Precision across the run is **44.8%**: more than half of what it raises is noise.

A reviewer that catches four bugs in ten and invents four in ten is not a filter. As a gate
it would reject a third of correct code; as advice it teaches people to ignore it.

The gap between `passing` (16.8%) and `reference` (38.8%) is worth noticing on its own. Both
are correct code. The difference is that one is the model's *own* output and the other is
somebody else's style - and unfamiliar style reads as suspicious.

## Running it

```bash
python run.py --limit 250
```

## Limits

- One review prompt. A different phrasing would move the flag rate, which is the point
  [prompt-shape-variance](../05_prompt_shape_variance) makes.
- "Has a bug" is a blunt question. A reviewer asked for specific classes of defect might
  behave very differently.
