<h1 align="center">temperature-pass-at-k</h1>
<p align="center"><i>The temperature you benchmark at is not the one you should deploy at.</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-60-blue" alt="">
  <img src="https://img.shields.io/badge/samples-5-ff7a18" alt="">
  <img src="https://img.shields.io/badge/estimator-unbiased%20pass@k-ffd21f" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

pass@1 rewards the single most likely answer, so low temperature wins. pass@k only
needs *one* of k samples to be right, so it rewards diversity &mdash; and greedy decoding
produces none.

Scored with the unbiased estimator `1 - C(n-c, k) / C(n, k)` rather than "did any of my k
samples pass", which is biased upward and shifts with how many you drew.

## Result

```
temp    pass@1   pass@2   pass@5   distinct/5
0.0      85.0%    85.0%    85.0%      1.0
0.4      83.3%    84.8%    85.0%      2.2
0.7      84.0%    87.5%    90.0%      3.0
1.0      84.7%    88.2%    90.0%      3.3
```

**The ordering flips. T=0 wins pass@1; T=0.7 wins pass@5 by
5.0%.**

The `distinct` column is the mechanism, not a footnote. At temperature 0 all five samples
are the same string &mdash; so pass@5 *cannot* exceed pass@1, and the first row is three
identical numbers.

The practical cost: **benchmark at T=0, deploy an agent that samples five times, and
5.0% of achievable pass@5 goes unclaimed.** Going the other
way is cheap &mdash; T=0.7 costs only 1.0% at k=1. If you
are unsure which regime you are in, the higher temperature loses much less.

## Running it

```bash
python run.py --limit 60 --samples 5
```

## Limits

- 60 tasks and 5 samples is a small sweep. **0.7 versus 1.0 at pass@5 is a tie here**
  (90.0% both) &mdash; the flip between k=1 and k=5 is the robust part, the
  exact optimum is not.
- Temperature 0 is generated once and copied rather than sampled five times, because the
  result is identical by construction.
