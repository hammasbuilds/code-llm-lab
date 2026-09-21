<h1 align="center">feedback-content</h1>
<p align="center"><i>When a fix fails, what part of the error message was doing the work?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/failures%2520retried-60-blue" alt="">
  <img src="https://img.shields.io/badge/best%2520arm-10.0%25-2ea44f" alt="">
  <img src="https://img.shields.io/badge/traceback%2520alone-1.7%25-b91c1c" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Take the 60 tasks the model got wrong on its first attempt and hand each failure back
five different ways. The arms are nested on purpose, so each one adds exactly one thing:

```
nothing      "that was wrong, try again"
boolean      + which assertion failed
assertion    + the text of the failing assert
traceback    + the Python traceback
expected     + the expected and actual values
```

## Result

```
nothing       1/60    1.7%
boolean       2/60    3.3%
assertion     6/60   10.0%   <- everything above this is noise
traceback     1/60    1.7%
expected      6/60   10.0%
```

**The assertion text is the whole signal.** Showing the failing assert takes the fix rate
from 1.7% to 10.0%. Adding the expected and actual values on top of it fixes *exactly the
same six tasks* - the sets are identical, not merely the same size.

**The traceback is worse than useless here**: 1.7%, the same as saying nothing at all. It is
the longest payload of the five and it fixed one task.

The practical version: if you are building a self-repair loop, send the assertion. The
traceback costs tokens and buys nothing, and the expected/actual values buy nothing beyond
what the assert already said.

And the ceiling is low regardless - 10% of first-attempt failures. That agrees with
[self-debug-ceiling](../02_self_debug_ceiling): the second attempt is not where the wins are.

## Running it

```bash
python run.py --limit 250
```

## Limits

- 60 failures is a small denominator; the gap between 1.7% and 10.0% is six tasks against one.
- MBPP assertions are short and literal. A failure inside a larger program produces a
  traceback that carries much more, and this result should not be read as "tracebacks are
  useless" in general.
