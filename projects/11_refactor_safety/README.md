<h1 align="center">refactor-safety</h1>
<p align="center"><i>Ask for a refactor that must not change behaviour. Does it hold?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/eligible-190-blue" alt="">
  <img src="https://img.shields.io/badge/worst%2520break%2520rate-32.6%25-b91c1c" alt="">
  <img src="https://img.shields.io/badge/broke%2520under%2520any-97-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Take solutions the model got right, ask for four behaviour-preserving refactors, and
re-run the original tests. A refactor that changes behaviour is a bug introduced by a request
that explicitly forbade it.

## Result

```
refactor        broke   renamed fn   broke logic
typehints        0.5%        0.5%          0.0%
extract          1.6%        0.5%          1.1%
rename          32.6%       32.6%          0.0%
idiomatic       32.1%       21.1%         11.1%
```

Splitting the failures apart is the whole result. **`rename` breaks a third of the time and
never once breaks the logic** - it renames the function the tests call. That is a
harness-shaped failure: the code is fine, the interface moved.

**`idiomatic` is the one to worry about.** It breaks at the same rate, but a third of its
failures are *logic* - 11.1% of refactors silently changed what the function computes, while
claiming to preserve it.

97 of 190 solutions broke under at least one refactor; exactly **1** broke under all four.
The risk is not that some code is fragile. It is that each refactor has its own failure mode.

## Running it

```bash
python run.py --limit 250
```

## Limits

- "Broke" means MBPP's tests fail. A refactor that changes untested behaviour is invisible
  here, and that gap is usually large -
  [suite-auditor](https://github.com/hammasbuilds/suite-auditor) exists because of it.
- Rename failures are arguably the harness's fault for calling the function by name. They are
  reported separately rather than excluded, because a caller elsewhere has the same problem.
