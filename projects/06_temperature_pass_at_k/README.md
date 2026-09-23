<h1 align="center">temperature-pass-at-k</h1>
<p align="center"><i>The temperature you benchmark at is not the one you should deploy at.</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-200-blue" alt="">
  <img src="https://img.shields.io/badge/pass@5%2520gain-%252B7.5pp-2ea44f" alt="">
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

200 tasks, five samples at each temperature.

```
temp     pass@1   pass@2   pass@5   distinct outputs
0.0      77.0%    77.0%    77.0%    1.0
0.4      75.9%    78.5%    81.5%    2.4
0.7      75.6%    80.3%    84.5%    3.1
1.0      74.5%    79.3%    83.5%    3.4
```

**The ordering flips with k.** T=0 is the best temperature for pass@1 and the worst for
pass@5. T=0.7 is the reverse.

```
best for pass@1 : T=0.0   77.0%
best for pass@5 : T=0.7   84.5%
```

At k=1, sampling costs you: T=0.7 gives up 1.4 points against greedy decoding. At k=5 it
gains 7.5. **Benchmark at T=0, deploy an agent that samples five times, and you leave 7.5
points of achievable pass@5 unclaimed** - and you would never see it, because the number you
tuned on says T=0 is correct.

T=0's five samples are identical by construction, so pass@5 equals pass@1 exactly. That
column is the control: it shows the benefit is coming from diversity and not from extra
attempts. T=1.0 has the most diverse outputs (3.4 distinct of 5) and does *worse* than T=0.7
at every k, so diversity is not the whole story either - there is an optimum, and it is not
at either end.

The practical version: **the temperature you benchmark at and the temperature you deploy at
are answers to different questions.** A published pass@1 is evidence about greedy decoding
and almost nothing else.

## Running it

```bash
python run.py --limit 200 --samples 5
```

## Limits

- 60 tasks and 5 samples is a small sweep. **0.7 versus 1.0 at pass@5 is a tie here**
  (90.0% both) &mdash; the flip between k=1 and k=5 is the robust part, the
  exact optimum is not.
- Temperature 0 is generated once and copied rather than sampled five times, because the
  result is identical by construction.
