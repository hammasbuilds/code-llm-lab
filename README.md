<h1 align="center">code-llm-lab (Python · MBPP/HumanEval · Ollama · mutation testing)</h1>
<p align="center"><i>Seven things worth measuring about a local coder model, none of them its benchmark score.</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="python">
  <img src="https://img.shields.io/badge/model-qwen2.5--coder-orange" alt="model">
  <img src="https://img.shields.io/badge/tests-15-brightgreen" alt="tests">
  <img src="https://img.shields.io/badge/gpu-1x%20RTX%205000-lightgrey" alt="gpu">
</p>

---

A pass@1 number tells you almost nothing you can act on. These seven ask questions that
change what you would actually build: whether the bigger model is worth its VRAM, when to
stop a self-debug loop, whether generated tests catch anything, and how much of a published
score is the prompt rather than the model.

Everything runs locally against Ollama. No API keys, no hosted models.

## 01 · Where does a 5x bigger model actually pay?

[`projects/01_coder_size_curve/`](projects/01_coder_size_curve/)

qwen2.5-coder at 3B and 14B — same family, same recipe, so the comparison is clean.
250 MBPP tasks, temperature 0.

```
3B  pass@1 : 60.0%
14B pass@1 : 76.0%

both         142   56.8%   the 14B bought nothing here
big_only      48   19.2%   this is what the size is for
small_only     8    3.2%   the 14B loses these
neither       52   20.8%
```

**Of the 198 tasks either size can solve, the 3B already handles 75.8%.** The 14B's entire
advantage is 48 tasks — and it *loses* 8 the 3B gets right, which bounds how much of the
16-point gap is signal rather than noise.

If your workload looks like MBPP, the question is not "which model is better" but "is 19.2%
of tasks worth 5x the weights", and the answer depends on what those 48 tasks are worth to
you. The aggregate score cannot tell you that.

## 02 · How many rounds of self-debugging are worth paying for?

[`projects/02_self_debug_ceiling/`](projects/02_self_debug_ceiling/)

Give the model its failing test output and let it try again, up to five times. 150 tasks.
Unlike a revision loop judged by another model, a failing assert is ground truth.

```
round 1: +117 solved   cumulative 78.0%
round 2:   +1 solved   cumulative 78.7%
round 3:   +0
round 4:   +0
round 5:   +0
```

**Rounds 1–2 captured 100% of everything the loop ever achieved. Rounds 3–5 added nothing
at all, for 60% of the compute.**

The 32 tasks still failing after round 1 were, with one exception, not tasks the model was
one nudge away from solving. They were tasks it could not do, and showing it the error five
times did not change that. Every agent looping five times on test feedback is paying five
times the tokens for the value of two.

## 03 · Do model-written tests catch anything?

[`projects/03_tests_that_kill/`](projects/03_tests_that_kill/)

"Write tests for this" judged by mutation kill rate rather than coverage — a test that
calls every line and asserts nothing has 100% coverage and catches nothing. 150 tasks.

```
                    valid   scored   asserts   kill rate
from_description    16.0%       19      12.1       88.9%
from_code           40.7%       48      11.0       93.4%
```

Two different findings here.

**Working from the task description, only 16% of suites even agree with the reference.**
Not because the tests are bad — because the sentence does not say whether the function
returns a list or a tuple, or what empty input does, and the model has to guess. That is a
measurement of the spec, not of the model.

**Working from the implementation, the tests are good.** On the suites that are valid:

```
model-written kill rate : 93.4%
MBPP's own kill rate    : 85.0%
difference              : +8.5%
```

The model wrote 3.7x as many asserts as MBPP ships and caught 8.5 points more of the
mutations. Generated tests are better than this benchmark's own — which says as much about
three-assert benchmarks as it does about the model. See
[mbpp-false-accepts](https://github.com/hammasbuilds/mbpp-false-accepts) for how thin three asserts are.

## 04 · Repair the failure, or throw it away and start over?

[`projects/04_repair_vs_rewrite/`](projects/04_repair_vs_rewrite/)

Agents almost always patch. The alternative — discard it and regenerate from the task — is
rarely tried and almost never compared. Both arms start from the same failed attempt and
get exactly one more call. 250 tasks, 60 first-attempt failures.

```
repair  fixed :  1  ( 1.7%)
rewrite fixed :  3  ( 5.0%)
neither       : 56  (93.3%)
```

**Neither works.** 93.3% of the failures survive both strategies. The gap between 1 and 3
out of 60 is not a result — it is two numbers inside the noise, and reporting "rewrite beats
repair by 3.3 points" from them would be wrong.

The real finding is the 93.3%, and it agrees with project 02 from a different direction:
the tasks a model fails on its first attempt are mostly tasks it *cannot do*, not tasks it
is one nudge away from. Retry strategies are a rounding error on MBPP. **What you get on
the first attempt is very nearly all you get.**

That is worth knowing before building an agent architecture around a retry loop.

## 05 · The same task, asked five ways

[`projects/05_prompt_shape_variance/`](projects/05_prompt_shape_variance/)

Five phrasings carrying identical information. Same model, same temperature, same tasks,
same execution rule — the only variable is wording. 200 tasks.

```
plain       78.5%
docstring   75.5%
comment     74.5%
signature   74.5%
terse       71.0%

spread       7.5%   attributable to formatting alone
```

7.5 points is worth knowing, but the sharper number is underneath it:

```
solved by at least one phrasing : 168  (84.0%)
solved by every phrasing        : 120  (60.0%)
flipped on phrasing alone       :  48  (24.0%)
```

**Just under a quarter of tasks are solved under one wording and failed under another.**
For those 48 the benchmark is not measuring whether the model can write the function. It is
measuring which sentence it was handed.

The aggregate hides this completely. A 7.5-point spread looks like noise you could average
away; a 24% flip rate means the per-task signal is much weaker than any single score
suggests, and that two papers reporting 74% and 78% on this benchmark may not disagree about
the model at all.

This is the input half of a pair. [code-eval-harness](https://github.com/hammasbuilds/code-eval-harness)
measured the output half: identical generations score 0% or 94% depending only on how code
is extracted from the response. Between them they bracket how much of a published pass@1
belongs to the harness rather than the model.

## 06 · The temperature you benchmark at is not the one you should deploy at

[`projects/06_temperature_pass_at_k/`](projects/06_temperature_pass_at_k/)

60 tasks, 5 samples each, scored with the unbiased pass@k estimator.

```
temp    pass@1   pass@2   pass@5   distinct/5
0.0      85.0%    85.0%    85.0%      1.0
0.4      83.3%    84.8%    85.0%      2.2
0.7      84.0%    87.5%    90.0%      3.0
1.0      84.7%    88.2%    90.0%      3.3
```

**The ordering flips. T=0 wins pass@1; T=0.7 wins pass@5 by five points.**

The `distinct` column is the mechanism, not a footnote. At temperature 0 all five samples
are the same string — so pass@5 *cannot* exceed pass@1, however large k gets, and the first
row shows three identical numbers. Raising temperature buys diversity, which pass@k rewards
and pass@1 mildly punishes.

The practical cost: **benchmark at T=0, deploy an agent that samples five times, and you
leave 5 points of achievable pass@5 unclaimed.** Going the other way is cheap — T=0.7 costs
only 1 point at k=1. The asymmetry matters: if you are unsure which regime you are in, the
higher temperature loses you much less than the lower one.

What this does not establish: 60 tasks and 5 samples is a small sweep, and 0.7 versus 1.0
at pass@5 is a tie here (90.0% both). The flip between k=1 and k=5 is the robust part; the
exact optimum is not.

## 07 · Code → prose → code. What survives the roundtrip?

[`projects/07_docstring_roundtrip/`](projects/07_docstring_roundtrip/)

Ask the model to describe the reference solution, hand that description to a fresh context,
and ask it to implement the function. Compare against implementing from MBPP's own task
description. 200 tasks.

```
from MBPP's description    : 48.0%
from the model's own prose : 80.5%
drift                      : +32.5%
```

**The roundtrip is 32.5 points better**, which is the opposite of the expected direction —
information is supposed to be lost, not gained. 73 tasks (36.5%) are solved from the
code-derived description and not from MBPP's; only 8 (4.0%) go the other way.

The explanation is not that the model writes good documentation. It is that **the
description was written with the answer in view.** It is a leak, not a spec. MBPP's
descriptions average 78 characters; the model's average 445, and those extra characters
encode decisions — return type, edge-case behaviour — that the task sentence never made.

That is the same finding project 03 reached from the other side: only 16% of test suites
written from MBPP's descriptions agree with the reference, because the descriptions do not
say what the function should return. Two independent measurements point at the task
descriptions as the weak link, not the model.

The practical version: **a docstring generated from an implementation cannot be used to
evaluate that implementation.** It is downstream of the code, so it agrees with it by
construction.

---

## All ten, at a glance

| # | Project | Headline |
|---|---|---|
| 01 | coder size curve | the 3B already handles **75.8%** of what either size can solve |
| 02 | self debug ceiling | rounds 1–2 = **100%** of the gain; rounds 3–5 = zero |
| 03 | tests that kill | **93.4%** kill rate vs MBPP's 85.0% — but only from code |
| 04 | repair vs rewrite | **93.3%** of failures survive both |
| 05 | prompt shape variance | **24%** of tasks flip on wording alone |
| 06 | temperature vs pass@k | optima flip; **5 points** lost by tuning on the wrong k |
| 07 | docstring roundtrip | the roundtrip beats the benchmark's own spec by **32.5 points** |

Two pairs corroborate each other from opposite directions, which is the part worth trusting:
**02 and 04** both say first-attempt failures are things the model cannot do, not things it
is one nudge from. **03 and 07** both say MBPP's task descriptions — not the model — are the
weak link.

## How it works

```
shared/datasets.py   MBPP and HumanEval normalised into one task shape
shared/execute.py    subprocess with a timeout; pass / fail / error / timeout kept apart
shared/model.py      Ollama over HTTP, with an on-disk generation cache
projects/NN_*/run.py one measurement each, self-contained
```

Three decisions that matter more than they look:

**Generation is batched.** One request at a time left the GPU at 9% utilisation — it spends
almost all of its time waiting for the next HTTP round trip rather than decoding. Eight
concurrent requests take it to ~98% and roughly halve wall-clock time.

**Generations are cached** by `(model, prompt, temperature, seed)`. Project 04's first
attempt completed in 3 seconds because project 01 had already asked those exact questions.

**`fail` and `error` are not merged.** Both mean the tests rejected the code, but only
`fail` means the tests actually tested something — a candidate caught by crashing would
have survived behind a guard clause.

## Running it

```bash
python projects/01_coder_size_curve/run.py --limit 250
python projects/03_tests_that_kill/run.py  --limit 150
```

Needs Ollama with `qwen2.5-coder:14b` (and `:3b` for project 01). MBPP and HumanEval load
from the local Hugging Face cache; nothing downloads at runtime.

## Limits

- **One model family, one size pair, one GPU.** Nothing here says how any of it scales.
- **MBPP is mostly short functions.** The self-debug ceiling in particular may look
  different on tasks where the first attempt is closer to right.
- **Temperature 0 throughout** except project 06, which is about temperature.
- Sample sizes are 60–250 tasks, chosen to fit an overnight GPU window. They are large
  enough to separate the effects reported and not large enough for small differences.
