<h1 align="center">constraint-compliance</h1>
<p align="center"><i>Tell it not to do something. Does it comply, and what does compliance cost?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-150-blue" alt="">
  <img src="https://img.shields.io/badge/worst%2520compliance-86%25-b8860b" alt="">
  <img src="https://img.shields.io/badge/accuracy%2520cost-under%25208pp-blue" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Six constraints, each stated plainly in the prompt, each checked by AST rather than by
asking. Two numbers per constraint: did it comply, and what did complying cost in pass@1.

The baseline column is the one that makes the rest mean anything - how often the constraint
holds when nobody asks for it.

## Result

```
constraint          complies   baseline   pass@1
none                       -          -    78.0%
type_hints              100%         0%    74.0%
no_recursion             99%        97%    77.3%
no_builtin_sort          98%        94%    70.7%
no_imports               96%        84%    78.7%
no_comprehensions        91%        81%    74.7%
single_return            86%        82%    76.0%
```

**Compliance is high, but most of it was free.** `no_recursion` reads as 99% obedience; the
model already avoids recursion 97% of the time unasked. The constraint moved two points.

**`type_hints` is the only one that is genuinely doing work**: 0% baseline to 100%
compliance. It is also the one nobody would have doubted.

**`single_return` is the hardest to obey** - 86%, against an 82% baseline, so asking bought
4 points. One request in seven is quietly ignored.

The cost is real but small: every constraint lands within 8 points of the 78.0% unconstrained
baseline, and `no_builtin_sort` is the most expensive at 7.3 points, which is what you would
expect from making it write its own sort.

## Running it

```bash
python run.py --limit 150
```

## Limits

- Compliance is checked syntactically. A model that satisfies the letter of "no imports" by
  inlining a library function counts as compliant.
- Six constraints on one benchmark. These are style rules, not the security or licensing
  constraints that would matter in production.
