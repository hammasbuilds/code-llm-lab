<h1 align="center">tests-that-kill</h1>
<p align="center"><i>Do model-written tests catch anything?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-500-blue" alt="">
  <img src="https://img.shields.io/badge/scored%20by-mutation%20kill%20rate-e879f9" alt="">
  <img src="https://img.shields.io/badge/arms-2-lightgrey" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

"Write tests for this" is one of the most common things anyone asks a coder model, and
the usual way to judge the answer is coverage. Coverage is a bad judge: a test that calls
every line and asserts nothing scores 100%.

So score them the way mutation testing does &mdash; break the reference solution in one
place and ask whether the tests notice.

## Result

```
                    valid   scored   asserts   kill rate
from_description     16.6%       64      10.6       90.7%
from_code            40.4%      164      10.6       93.8%
```

Two separate findings.

**Written from the implementation, the tests are good.** On the 164 valid suites (723
mutants) the model kills **93.8%** against MBPP's own **85.5%** on the same tasks &mdash;
**+8.3 points**, using 3.5&times; as many asserts. Generated tests beat the benchmark's own.

**Written from the task description, only 16.6% of suites even agree with the reference.**
Not because the tests are bad &mdash; the sentence never says whether the function returns a
list or a tuple, or what empty input should do, so the model guesses. That number measures
the *spec*, not the model.

Both numbers held across a 3.3&times; increase in tasks: at 150 they read 16.0% / 40.7%
valid and 93.4% vs 85.0% on kill rate. The `scored` column is the one that improved, from 48
suites to 164 &mdash; the +8.3 point gap now rests on a denominator that can carry it.

[docstring roundtrip](../07_docstring_roundtrip) reaches the same conclusion from the
opposite side.

## Why two arms

The first version of this project had only the description arm and produced nothing
scorable, because almost no suite passed the reference. That failure was the finding, and
splitting it in two is what separates "the spec was too thin" from "the tests were bad".

## Running it

```bash
python run.py --limit 500 --per-problem 8
```

Reuses the mutation engine from
[mbpp-false-accepts](https://github.com/hammasbuilds/mbpp-false-accepts).

## Limits

- Only suites that pass the reference can have a meaningful kill rate, so the scored
  denominators (19 and 48) are smaller than 150.
- Mutation kill rate is a proxy. It rewards catching *changes*, which is not identical to
  catching *bugs a person would write*.
