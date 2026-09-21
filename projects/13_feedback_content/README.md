<h1 align="center">feedback-content</h1>
<p align="center"><i>When a fix fails, what part of the error message was doing the work?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/failures%2520retried-191-blue" alt="">
  <img src="https://img.shields.io/badge/best%2520arm-15.2%25-2ea44f" alt="">
  <img src="https://img.shields.io/badge/no%2520feedback-7.9%25-64748b" alt="">
  <img src="https://img.shields.io/badge/p-0.0013-2ea44f" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Take the 191 tasks the model got wrong on its first attempt across all 972 MBPP problems
and hand each failure back five different ways. The arms are nested on purpose, so each one
adds exactly one thing:

```
nothing      "that was wrong, try again"
boolean      + which assertion failed
assertion    + the text of the failing assert
traceback    + the Python traceback
expected     + the expected and actual values
```

Every arm retries the same 191 tasks, so the comparison is paired and the p-values below
are exact McNemar tests on the discordant pairs - the tasks one arm fixed and the other
did not.

## Result

```
                fixed          vs "nothing"
nothing       15/191   7.9%        -
boolean       16/191   8.4%    p = 1.00      <- saying "it failed" is saying nothing
assertion     29/191  15.2%    p = 0.0013    <- the signal
traceback     18/191   9.4%    p = 0.25
expected      24/191  12.6%    p = 0.035
```

**The assertion text is the signal.** Showing the failing assert nearly doubles the fix
rate, 7.9% to 15.2%, and it is the only arm that clears significance comfortably. Telling
the model *that* it failed without showing the assert (`boolean`) is worth nothing at all:
three tasks gained, two lost, p = 1.00.

**Adding the expected and actual values makes it worse, not better.** `expected` fixes 24
where `assertion` fixes 29, and 23 of its 24 are a subset of `assertion`'s - it is the same
signal with 38 more characters of padding and five fewer fixes. That is the opposite of
what the 250-task run suggested, where the two arms fixed an identical set of six tasks and
looked interchangeable.

Per character, the ranking is the same and sharper:

```
             extra chars    extra fixes    cost per fix
assertion         17,730             14       1,266
traceback          8,128              3       2,709
expected          24,988              9       2,776
boolean            5,348              1       5,348
```

**The ceiling is low regardless.** Across all five framings only **34 of 191** failures were
ever fixed by any of them - 17.8%. Four fifths of first-attempt failures are not a
communication problem, which agrees with [self-debug-ceiling](../02_self_debug_ceiling):
the second attempt is not where the wins are.

### What the small run got wrong

At 250 tasks this repository reported that the traceback was **"worse than useless - the
same as saying nothing at all"**, on 1 fixed task out of 60. At 972 it fixes 18 of 191
against the baseline's 15, p = 0.25. That is not "worse than useless"; it is *not
distinguishable from the baseline*, which is a weaker and much less interesting claim. The
original sentence was one task's worth of noise written up as a finding.

The practical advice survives and is now worth stating: **send the assert, send nothing
else.** The traceback costs tokens and buys nothing measurable, and the expected/actual
values actively cost you fixes.

## Running it

```bash
python run.py --limit 972
```

## Limits

- One model (`qwen2.5-coder:14b`) at temperature 0, one retry per arm. Whether a stronger
  model needs less of the message is not measured here.
- MBPP assertions are short and literal, and the whole program is one function. A failure
  deep inside a larger program produces a traceback carrying much more than MBPP's does,
  and none of this should be read as "tracebacks are useless" in general.
- The arms are nested, so `expected` contains everything `assertion` contains. It fixing
  *fewer* tasks means longer prompts cost something, not that the extra values are harmful
  on their own.
