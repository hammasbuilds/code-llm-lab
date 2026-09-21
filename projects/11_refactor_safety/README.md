<h1 align="center">refactor-safety</h1>
<p align="center"><i>Ask for a refactor that must not change behaviour. Does it hold?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/eligible-781-blue" alt="">
  <img src="https://img.shields.io/badge/worst%2520break%2520rate-33.2%25-b91c1c" alt="">
  <img src="https://img.shields.io/badge/silent%2520logic%2520change-9.2%25-b91c1c" alt="">
  <img src="https://img.shields.io/badge/broke%2520under%2520any-393-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Take the 781 solutions the model got right across all 972 MBPP tasks, ask for four
behaviour-preserving refactors, and re-run the original tests. A refactor that changes
behaviour is a bug introduced by a request that explicitly forbade it.

## Result

```
refactor        broke   renamed fn   broke logic   mean chars
typehints        1.4%        1.3%          0.1%    164 -> 201
extract          3.3%        1.7%          1.7%    164 -> 225
rename          31.8%       31.6%          0.1%    164 -> 217
idiomatic       33.2%       23.9%          9.2%    164 -> 124
```

Splitting the failures apart is the whole result. **`rename` breaks a third of the time and
almost never breaks the logic** - 247 of its 248 failures are the function the tests call
being renamed. That is a harness-shaped failure: the code is fine, the interface moved.

**`idiomatic` is the one to worry about.** It breaks at the same headline rate, but **72 of
its 259 failures are logic** - 9.2% of all idiomatic refactors silently changed what the
function computes while claiming to preserve it. It is also the only refactor that makes the
code *shorter*, 164 characters to 124, and shortening is where behaviour goes missing.

393 of 781 solutions broke under at least one refactor; **9** broke under all four. The risk
is not that some code is fragile. It is that each refactor has its own failure mode, and
they barely overlap.

### What four times the data changed

The 250-task run put `idiomatic`'s silent logic-change rate at 11.1% on 190 eligible
solutions. At 781 it is 9.2% - the same finding with a denominator that can carry it. Two
numbers did move enough to matter:

- `typehints` went from 0.5% to 1.4% broken, and `extract` from 1.6% to 3.3%. Both were
  single-digit counts before (1 and 3 failures); they are now 11 and 26.
- `extract`'s failures turned out to be **half logic changes** (13 of 26), not the renames
  the small run suggested. It is a quiet third place behind `idiomatic`.

## Running it

```bash
python run.py --limit 972
```

## Limits

- "Broke" means MBPP's tests fail. A refactor that changes untested behaviour is invisible
  here, and that gap is large: MBPP's three asserts accept 17.6% of provably wrong programs
  ([mbpp-false-accepts](https://github.com/hammasbuilds/mbpp-false-accepts)). **Every logic
  rate here is a lower bound.**
- Rename failures are arguably the harness's fault for calling the function by name. They are
  reported separately rather than excluded, because a caller elsewhere has the same problem.
- One model, temperature 0, one refactor attempt each.
