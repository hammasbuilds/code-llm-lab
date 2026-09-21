<h1 align="center">repair-vs-rewrite</h1>
<p align="center"><i>Patch the failure, or throw it away and start over?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-972-blue" alt="">
  <img src="https://img.shields.io/badge/failures-191-ef6461" alt="">
  <img src="https://img.shields.io/badge/survived%20both-81.7%25-red" alt="">
  <img src="https://img.shields.io/badge/repair%20vs%20rewrite-p%3D0.72-64748b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Agents almost always patch. The alternative &mdash; discard it and regenerate from the
task &mdash; is rarely tried and almost never compared, even though the two have different
costs. Repair sends the broken code back in the prompt, so it costs more tokens *and*
anchors the model on an approach that already failed.

Both arms start from the same failed attempt and get exactly one more call, so the
comparison is paired across all 191 failures.

## Result

```
first attempt pass@1 : 80.3%   (191 failures to work with)

repair  fixed :  18  (9.4%)
rewrite fixed :  21  (11.0%)
both          :   4
neither       : 156  (81.7%)
```

**Most failures survive both.** 81.7% are fixed by neither strategy.

This project still deliberately does **not** report "rewrite beats repair". The gap is 1.6
points, and paired it is 14 tasks repair fixed alone against 17 rewrite fixed alone -
an exact McNemar p of **0.72**. Four times the data turned an anecdote into a clear
negative: the two strategies are not distinguishable.

### What the bigger denominator did show

At 250 tasks the overlap between the arms was zero out of four fixes, which is what zero
overlap always looks like when there is nothing to overlap. At 972 the picture is legible:

```
repair only   14
rewrite only  17
both           4      <- only 4 of 35
either        35  (18.3%)
```

**The two strategies fix almost disjoint sets.** Either one alone recovers about a tenth of
the failures; running both recovers 18.3%, nearly double, because they so rarely succeed on
the same task. That is the useful finding, and it is the opposite of the question everyone
asks - the choice between them matters much less than the decision to do both.

It agrees with [self-debug ceiling](../02_self_debug_ceiling) from another angle: tasks a
model fails on its first attempt are mostly tasks it *cannot do*, not tasks it is one nudge
away from. But the disjointness means a retry loop is not quite the rounding error the
250-task run made it look - 18.3% of failures is worth having, if you are willing to pay
for two calls instead of one.

## Running it

```bash
python run.py --limit 972
```

## Limits

- One retry each, one model, temperature 0. A five-round loop was measured separately in
  [self-debug ceiling](../02_self_debug_ceiling) and added nothing after round 2.
- The two arms use different seeds (1 and 2), so part of the disjointness is ordinary
  sampling variance rather than a property of the strategies. A same-seed rewrite arm would
  separate those and is not run here.
- 191 failures supports the 81.7% comfortably and is still too small to detect a difference
  between the arms smaller than roughly 8 points.
