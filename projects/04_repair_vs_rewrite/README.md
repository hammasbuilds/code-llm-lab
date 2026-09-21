<h1 align="center">repair-vs-rewrite</h1>
<p align="center"><i>Patch the failure, or throw it away and start over?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-250-blue" alt="">
  <img src="https://img.shields.io/badge/failures-60-ef6461" alt="">
  <img src="https://img.shields.io/badge/survived%20both-93.3%25-red" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Agents almost always patch. The alternative &mdash; discard it and regenerate from the
task &mdash; is rarely tried and almost never compared, even though the two have different
costs. Repair sends the broken code back in the prompt, so it costs more tokens *and*
anchors the model on an approach that already failed.

Both arms start from the same failed attempt and get exactly one more call.

## Result

```
first attempt pass@1 : 76.0%   (60 failures to work with)

repair  fixed :  1  (1.7%)
rewrite fixed :  3  (5.0%)
both          :  0
neither       : 56  (93.3%)
```

**Neither strategy works.** 93.3% of the failures survive both.

This project deliberately does **not** report "rewrite beats repair".
3 against 1 out of 60 is two numbers inside the
noise, and dressing that up as a result would be wrong. The finding is the
93.3%.

It agrees with [self-debug ceiling](../02_self_debug_ceiling) from another angle: tasks a
model fails on its first attempt are mostly tasks it *cannot do*, not tasks it is one nudge
away from. Retry strategies are a rounding error on MBPP &mdash; worth knowing before
building an agent around a retry loop.

## Running it

```bash
python run.py --limit 250
```

## Limits

- 60 failures is a small denominator. It is large enough to establish that the survival
  rate is high and too small to rank the two strategies.
- One retry each. A five-round loop was measured separately and added nothing after round 2.
