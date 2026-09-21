<h1 align="center">coder-size-curve</h1>
<p align="center"><i>Where does a 5&times; bigger model actually pay?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-972-blue" alt="">
  <img src="https://img.shields.io/badge/model-qwen2.5--coder-orange" alt="">
  <img src="https://img.shields.io/badge/benchmark-MBPP-lightgrey" alt="">
  <img src="https://img.shields.io/badge/3B%20covers-74.8%25-2ea44f" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

qwen2.5-coder ships at 3B and 14B: same family, same recipe, same tokenizer. That makes
the size comparison clean in a way that comparing across families never is.

"The 14B scores higher" is not useful. The question worth asking is *where* the extra
7.6&nbsp;GB of weights goes.

## Result

All 972 MBPP tasks, both sizes, temperature 0.

```
3B  pass@1 : 62.9%
14B pass@1 : 80.3%

both         575   59.2%   the 14B bought nothing here
big_only     206   21.2%   this is what the size is for
small_only    36    3.7%   the 14B lost these
neither      155   15.9%   size was not the problem
```

**Of the 817 tasks either size can solve, the 3B already handles 74.8%.** The 14B's entire
advantage is 206 tasks &mdash; and it *loses* 36 the 3B gets right.

That reframes the deployment question. Not "which model is better" but "is 21.2% of tasks
worth five times the weights", and an aggregate score cannot answer it.

### The 36 regressions are the number that survived scaling up

At 250 tasks the 3B won 8 tasks, and this README called those 8 "the honest noise floor".
That reading does not survive the full corpus. 206 against 36 is an exact McNemar
p of **4&times;10&#8315;&#179;&#8304;** &mdash; the size advantage is not in doubt &mdash; but the
regression rate itself held steady at 3.2% then and 3.7% now. It is not noise that shrinks
with more data; it is a stable property of the pair.

**Roughly one task in 27 gets worse when you scale this family up 5&times;.** If you are
swapping a 3B for a 14B in something already in production, that is the number to plan
around, and it is invisible in the 17.4-point headline gap.

## Running it

```bash
python run.py --limit 972              # MBPP
python run.py --benchmark humaneval    # the other one
```

Needs Ollama with both `qwen2.5-coder:3b` and `qwen2.5-coder:14b`.

## Limits

- One family, one size pair, one sample at temperature 0. Nothing here says how this scales
  to 70B or across families.
- Single-sample at temperature 0 means the 36 regressions are not separated into "the 14B
  cannot do this" and "the 14B did not do this on the one attempt it got". Distinguishing
  those needs pass@k, which [temperature-pass-at-k](../06_temperature_pass_at_k) measures
  on a smaller task set.
- MBPP is mostly short functions; the gap may widen on longer ones.
