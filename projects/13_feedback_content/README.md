<h1 align="center">feedback-content</h1>
<p align="center"><i>When a fix fails, what part of the error message was doing the work?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/failures%2520retried-191-blue" alt="">
  <img src="https://img.shields.io/badge/best%2520arm-18.3%25-2ea44f" alt="">
  <img src="https://img.shields.io/badge/no%2520feedback-8.4%25-64748b" alt="">
  <img src="https://img.shields.io/badge/length%2520alone-7.3%25-b91c1c" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Take the 191 tasks the model got wrong on its first attempt across all 972 MBPP problems
and hand each failure back six different ways:

```
nothing      "that was wrong, try again"
boolean      + the tests failed, no detail
assertion    the assert that failed, and nothing else
traceback    the real traceback: exception, source line, caret
expected     the failing assert plus what the code produced instead
padding      a control - matched to `expected`'s length, character for character,
             with true statements about the harness that say nothing about the failure
```

The arms **replace** each other rather than nesting. Every arm retries the same 191 tasks,
so the comparison is paired and the p-values are exact McNemar tests on the discordant
tasks - the ones where one arm succeeded and the other did not.

## Result

```
                fixed          vs "nothing"     prompt
padding       14/191   7.3%    p = 0.63          548 chars   <- length alone
nothing       16/191   8.4%       -              426
boolean       19/191   9.9%    p = 0.38          454         <- "it failed" is not information
traceback     27/191  14.1%    p = 0.013         643
assertion     29/191  15.2%    p = 0.0023        518
expected      35/191  18.3%    p = 0.0003        548         <- best
```

**The padding control is the result.** It is exactly as long as the best arm - 548
characters against 548 - and it scores **below the no-feedback baseline**. Length buys
nothing. Whatever the informative arms gained, they gained from what they said, and that is
now measured rather than assumed.

**Showing the model the actual value is the most useful single thing you can do.** `expected`
more than doubles the baseline, 8.4% to 18.3%, at 122 characters. Its edge over `assertion`
alone (+9 tasks, -3) is **not** individually significant at p = 0.15, so the honest ranking
is "`expected` and `assertion` are the two strong arms, `expected` ahead" - not "`expected`
beats `assertion`".

**Telling it that it failed, without telling it how, is worth nothing.** `boolean` adds 28
characters and 3 tasks, p = 0.38.

Per character bought:

```
             extra chars    extra fixes    cost per fix
expected          23,373             19       1,230
assertion         17,730             13       1,364
boolean            5,348              3       1,783
traceback         41,563             11       3,778
padding           23,373             -2         n/a
```

The traceback works, but it is the **most expensive** way to say it: the longest payload of
the six, carrying the same assert line the cheap arm carries, for three times the cost per
fix.

**The ceiling is 22.0%.** Across all six framings only 42 of 191 failures were ever fixed by
any of them. Four fifths of first-attempt failures are not a communication problem, which
agrees with [self-debug-ceiling](../02_self_debug_ceiling).

### This project previously reported the opposite, because of a harness bug

Two earlier runs concluded the traceback was **"worse than useless - the same as saying
nothing at all"**. That was not a fact about tracebacks. The arm was never sent one.

`Outcome.detail` is the **last line** of stderr, and for an `AssertionError` that line is
the bare word `AssertionError` - fourteen characters, no file, no line, no source, no
values. So the arm's entire payload was:

```
Running the tests gave:
AssertionError
```

which is the `boolean` arm reworded. The two scored alike because they *were* alike. Sent a
real traceback, the arm clears the baseline at p = 0.013.

The `expected` arm was broken in the same family. Its value probe *prints* the answer, so
the probe succeeds - and a successful `Outcome` carries no `detail`. The code read `detail`,
so it returned `(could not be evaluated)` precisely when the value was available, for every
task in both runs. The tell was in the committed results file: `expected` minus `assertion`
was **38.0000000000** characters, a constant, and `len("It produced: (could not be
evaluated)\n")` is exactly 38. Real values do not all have the same length.

That bug also produced a wrong *explanation*. `expected` scored below `assertion`, and the
write-up attributed it to longer prompts costing something. It was not length - the extra
text was noise announcing that the harness had failed. The `padding` arm exists so that
question is now settled by a control instead of by a plausible story.

Both bugs are pinned by tests in `tests/test_shared.py`, and the same `.detail` misuse was
found and fixed in [self-debug-ceiling](../02_self_debug_ceiling) and
[repair-vs-rewrite](../04_repair_vs_rewrite), which were feeding it into repair prompts.

## Running it

```bash
python run.py --limit 972
```

## Limits

- One model (`qwen2.5-coder:14b`) at temperature 0, one retry per arm, one seed per arm.
  A task that flips is one coin, not a rate.
- `padding` controls for **length**, not layout: it matches `expected`'s character count
  exactly but is one unbroken line where `expected` has newlines.
- 17 of 191 failures genuinely have no recoverable value - the call raises or does not
  terminate - and `expected` degrades to `(could not be evaluated)` on those, which is now
  what that string honestly means.
- MBPP assertions are short and literal and the whole program is one function. A traceback
  from deep inside a larger program carries far more than MBPP's does, so the "traceback is
  expensive per fix" result should not be read as a general claim.
