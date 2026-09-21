<h1 align="center">coder-size-curve</h1>
<p align="center"><i>Where does a 5&times; bigger model actually pay?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-250-blue" alt="">
  <img src="https://img.shields.io/badge/model-qwen2.5--coder-orange" alt="">
  <img src="https://img.shields.io/badge/benchmark-MBPP-lightgrey" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

qwen2.5-coder ships at 3B and 14B: same family, same recipe, same tokenizer. That makes
the size comparison clean in a way that comparing across families never is.

"The 14B scores higher" is not useful. The question worth asking is *where* the extra
7.6&nbsp;GB of weights goes.

## Result

```
3B  pass@1 : 60.0%
14B pass@1 : 76.0%

both         142   the 14B bought nothing here
big_only      48   this is what the size is for
small_only     8   the 14B lost these
neither       52   size was not the problem
```

**Of the 198 tasks either size can solve, the 3B already handles
75.8%.** The 14B's entire advantage is 48 tasks
&mdash; and it *loses* 8 the 3B gets right, which puts a floor under how
much of the 16.0% gap is capability
rather than variance.

That reframes the deployment question. Not "which model is better" but "is
19.2% of tasks worth five times the weights" &mdash; and an
aggregate score cannot answer it.

## Running it

```bash
python run.py --limit 250              # MBPP
python run.py --benchmark humaneval    # the other one
```

Needs Ollama with both `qwen2.5-coder:3b` and `qwen2.5-coder:14b`.

## Limits

- One family, one size pair. Nothing here says how this scales to 70B or across families.
- MBPP is mostly short functions; the gap may widen on longer ones.
- The 8 tasks the 3B wins are the honest noise floor &mdash; treat
  differences smaller than that as unmeasured.
