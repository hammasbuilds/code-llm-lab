# Seven findings in full

[<- back to the README](../README.md)

The projects table in the README gives every finding in one line, and each project has its
own README with its method, its limits and what it got wrong. These seven are written out at
length because they are the ones where the *reasoning* is the point - a control that changes
the answer, a number that reversed, a result that is only interesting next to its baseline.

The other thirteen are no less real; they are just shorter to state.

---


### 01 · Where does a 5x bigger model actually pay? — 972 tasks

qwen2.5-coder at 3B and 14B — same family, same recipe, so the comparison is clean.

```
3B  pass@1 : 62.9%
14B pass@1 : 80.3%

both         575   59.2%   the 14B bought nothing here
big_only     206   21.2%   this is what the size is for
small_only    36    3.7%   the 14B loses these
neither      155   15.9%
```

**Of the 817 tasks either size can solve, the 3B already handles 74.8%.** The 14B's entire
advantage is 206 tasks — and it *loses* 36 the 3B gets right.

If your workload looks like MBPP, the question is not "which model is better" but "is 21.2%
of tasks worth 5x the weights", and the answer depends on what those 206 tasks are worth to
you. The aggregate score cannot tell you that.

The 36 regressions are the number that survived scaling the run up. At 250 tasks this
README called the 8 the 3B won "the noise floor"; the rate barely moved, 3.2% to 3.7%.
**Roughly one task in 27 gets worse when you scale this family up 5x**, and that is
invisible in the headline gap.

It is also the number that survived splitting the corpus: 3.6% on MBPP's held-out test
split, 3.2% on its training split. The size *advantage* does not survive as cleanly — it is
+19.9 points on the contaminated half and **+16.2 on the held-out 500**.

- **Stack:** Ollama, `qwen2.5-coder:3b` and `:14b`, MBPP
- **In:** a task and a model size
- **Out:** pass@1 for each size **and the four-way bucket split** — which is the part an
  aggregate score destroys, because `both` and `neither` cancel out of the difference

### 02 · How many rounds of self-debugging are worth paying for? — 500 tasks

Give the model its failing test output and let it try again, up to five times. Unlike a
revision loop judged by another model, a failing assert is ground truth.

```
round 1: +381 solved   cumulative 76.2%    94.5% of the total gain
round 2:  +19 solved   cumulative 80.0%     4.7%
round 3:   +2           cumulative 80.4%     0.5%
round 4:   +1           cumulative 80.6%     0.2%
round 5:   +0           cumulative 80.6%     0.0%
```

**Rounds 1–2 captured 99.3% of everything the loop ever achieved. Rounds 3–5 added three
tasks — 0.6% of the benchmark — for 60% of the compute.**

The tasks still failing after round 2 were not tasks the model was one nudge away from
solving. They were tasks it could not do, and showing it the error three more times did not
change that. Every agent looping five times on test feedback is paying five times the tokens
for the value of two.

This number was in doubt until it was re-run. Every round used to be shown the bare string
`AssertionError` rather than a real error, and a loop given no information plateauing
immediately is exactly what that bug would produce. Re-measured with a real traceback, the
plateau is unchanged — unlike [13](projects/13_feedback_content/), which had the same bug and
reversed outright.

- **Stack:** Ollama, `qwen2.5-coder:14b`, MBPP
- **In:** a task, and on every round after the first, the model's own code plus the real
  test output it produced
- **Out:** newly solved per round, so a plateau is visible as a shape rather than inferred
  from a final total. Each round is seeded separately, or the cache would hand back round
  one's answer and the flat curve would be an artefact

### 03 · Do model-written tests catch anything? — 500 tasks

"Write tests for this" judged by mutation kill rate rather than coverage — a test that
calls every line and asserts nothing has 100% coverage and catches nothing.

```
                    valid   scored   asserts   kill rate
from_description    16.6%       64      10.6       90.7%
from_code           40.4%      164      10.6       93.8%
```

Two different findings here.

**Working from the task description, only 16.6% of suites even agree with the reference.**
Not because the tests are bad — because the sentence does not say whether the function
returns a list or a tuple, or what empty input does, and the model has to guess. That is a
measurement of the spec, not of the model.

**Working from the implementation, the tests are good.** On the suites that are valid:

```
model-written kill rate : 93.8%
MBPP's own kill rate    : 85.5%
difference              : +8.3%
```

The model wrote 3.5x as many asserts as MBPP ships and caught 8.3 points more of the
mutations. Generated tests are better than this benchmark's own — which says as much about
three-assert benchmarks as it does about the model. See
[mbpp-false-accepts](https://github.com/hammasbuilds/mbpp-false-accepts) for how thin three
asserts are.

- **Stack:** Ollama, `qwen2.5-coder:14b`, MBPP, stdlib `ast` for mutation
- **In:** a task description *or* the reference implementation — the two arms
- **Out:** kill rate against 8 single-point mutants per task, scored **against MBPP's own
  suite on the same mutants**, so the comparison is like for like

### 04 · Repair the failure, or throw it away and start over? — 972 tasks

Agents almost always patch. The alternative — discard it and regenerate from the task — is
rarely tried and almost never compared. Both arms start from the same failed attempt and
get exactly one more call. 191 first-attempt failures.

```
repair  fixed :  27  (14.1%)
rewrite fixed :  21  (11.0%)
both          :   4
neither       : 147  (77.0%)
```

**Most failures survive both.** The 3.1-point gap is not a result: paired, it is 23 tasks
repair fixed alone against 17 rewrite fixed alone, an exact McNemar p of **0.43**.

What the full corpus shows is that **the two fix almost disjoint sets** — only 4 of 44
successes overlap. Either alone recovers about an eighth of the failures; both together
recover 23.0%.

This arm was also where the `AssertionError` bug did the most damage, because it handicaps
only the side that reads an error message. Repaired with a real traceback, repair went
18 → 27 fixes (p=0.035) while rewrite returned **the identical 21 tasks, one for one** —
the control that makes the rest of it believable.

So the agreement with project 02 needs qualifying, and 02 is being re-measured with the same
fix. The tasks a model fails first time are mostly tasks it *cannot do* — 77.0% survive
everything — but 23.0% do not, and that is no longer a rounding error.

- **Stack:** Ollama, `qwen2.5-coder:14b`, MBPP
- **In:** one failed attempt, and a strategy — patch it, or bin it and start again
- **Out:** both arms on the same 60 failures, under **different seeds**, or the cache would
  serve the rewrite arm the repair arm's generation and the comparison would be vacuous

### 05 · The same task, asked five ways — 972 tasks

Five phrasings carrying identical information. Same model, same temperature, same tasks,
same execution rule — the only variable is wording.

```
plain       80.6%
comment     80.1%
signature   79.8%
terse       79.2%
docstring   78.5%

spread       2.1%   attributable to formatting alone   (stdev 0.7%)
```

The aggregate barely moves. Two points between best and worst, standard deviation under
one. On the score alone you would say prompt shape does not matter here. Underneath it:

```
solved by at least one phrasing : 860  (88.5%)
solved by every phrasing        : 642  (66.0%)
flipped on phrasing alone       : 218  (22.4%)
```

**218 tasks are solved under one wording and failed under another** — while the scores
those wordings produce sit within two points of each other. For those 218 the benchmark is
not measuring whether the model can write the function. It is measuring which sentence it
was handed.

Both numbers together are the finding. **A stable aggregate is not evidence of stable
behaviour.** The phrasings agree on the total almost exactly *because* the tasks each one
wins and loses cancel out, not because they solve the same tasks. There is also 8 points of
headroom nobody collects: the best single phrasing reaches 80.6%, but 88.5% of tasks are
solvable by some phrasing.

At 200 tasks the spread read 7.5 points and the flip rate 24%. Five times the data took two
thirds off the spread and left the flip rate within 1.6 points — which is what the earlier
write-up predicted would happen, having called the spread noise and the flip rate the real
quantity.

This is the input half of a pair.
[code-eval-harness](https://github.com/hammasbuilds/code-eval-harness) measured the output
half: identical generations score 0% or 94% depending only on how code is extracted from the
response. Between them they bracket how much of a published pass@1 belongs to the harness
rather than the model.

- **Stack:** Ollama, `qwen2.5-coder:14b`, MBPP
- **In:** one task, rendered five ways — plain, docstring, comment, signature, terse
- **Out:** pass@1 per shape **and the per-task flip set**, because the spread and the flip
  rate are different claims and only the second one bounds the per-task signal

### 06 · The temperature you benchmark at is not the one you should deploy at — 60 tasks

5 samples each, scored with the unbiased pass@k estimator `1 - C(n-c,k)/C(n,k)`.

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

- **Stack:** Ollama, `qwen2.5-coder:14b`, MBPP
- **In:** a task, a temperature, and 5 draws
- **Out:** pass@1/2/5 by the unbiased estimator, **with distinct-sample count beside it** —
  the naive "any of k passed" is biased upward and shifts with n, which makes numbers from
  different papers incomparable

### 07 · Code → prose → code. What survives the roundtrip? — 972 tasks

Ask the model to describe the reference solution, hand that description to a fresh context,
and ask it to implement the function. Compare against implementing from MBPP's own task
description.

```
from MBPP's description    : 51.6%
from the model's own prose : 83.3%
drift                      : +31.7%
```

**The roundtrip is 31.7 points better**, which is the opposite of the expected direction —
information is supposed to be lost, not gained. 333 tasks (34.3%) are solved from the
code-derived description and not from MBPP's; only 25 (2.6%) go the other way. That is a
thirteen-to-one exchange, not a trade.

The explanation is not that the model writes good documentation. It is that **the
description was written with the answer in view.** It is a leak, not a spec. MBPP's
descriptions average 79 characters; the model's average 444, and those extra characters
encode decisions — return type, edge-case behaviour — that the task sentence never made.

That is the same finding project 03 reached from the other side: only 16.6% of test suites
written from MBPP's descriptions agree with the reference, because the descriptions do not
say what the function should return. Two independent measurements point at the task
descriptions as the weak link, not the model.

The practical version: **a docstring generated from an implementation cannot be used to
evaluate that implementation.** It is downstream of the code, so it agrees with it by
construction.

- **Stack:** Ollama, `qwen2.5-coder:14b`, MBPP
- **In:** either MBPP's task sentence or the model's own description of the reference
- **Out:** pass@1 per arm, plus the **gained and lost task sets** — the direction of the
  drift is the finding, and a single drift number cannot show it
