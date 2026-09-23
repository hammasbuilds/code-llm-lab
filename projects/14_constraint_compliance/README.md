<h1 align="center">constraint-compliance</h1>
<p align="center"><i>Tell it not to do something. Does it comply, and what does compliance cost?</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/tasks-972-blue" alt="">
  <img src="https://img.shields.io/badge/type__hints-0%25%2520%25E2%2586%2592%2520100%25-2ea44f" alt="">
  <img src="https://img.shields.io/badge/no__recursion%2520baseline-96%25-b8860b" alt="">
</p>

<p align="center"><a href="../../README.md">&larr; code-llm-lab</a></p>

---

Six constraints, each stated plainly in the prompt, each checked by AST rather than by
asking. Two numbers per constraint: did it comply, and what did complying cost in pass@1.

The baseline column is the one that makes the rest mean anything - how often the constraint
holds when nobody asks for it.

## Result

All 972 MBPP tasks, one arm per constraint plus an unconstrained control.

```
constraint            already  complied   pass@1  vs control
no_recursion              96%       99%    79.1%     -1.2%
no_imports                79%       96%    77.8%     -2.6%
no_comprehensions         80%       92%    77.9%     -2.5%
no_builtin_sort           94%       98%    76.6%     -3.7%
type_hints                 0%      100%    79.1%     -1.2%
single_return             79%       85%    77.9%     -2.5%
```

**The `already` column is the finding.** It is how often the *unconstrained* control
satisfies the rule by habit, and without it every constraint looks obeyed.

`no_recursion` reads 99% compliance, which sounds like near-perfect instruction-following
until you see that the model was already writing non-recursive code 96% of the time. The
instruction moved it three points. `no_builtin_sort` moved it four. Those are not
measurements of obedience; they are measurements of what the model does anyway.

**Only `type_hints` does real work: 0% to 100%.** It is the one constraint the model never
satisfies by accident, and it is followed completely when asked. That single row is worth
more than the other five together, because it is the only one where compliance and habit
are distinguishable.

**Constraints cost accuracy, and consistently.** Every arm loses ground against the 80.3%
control, between 1.2 and 3.7 points. The cost does not track how hard the constraint is to
satisfy: `no_builtin_sort` is the most expensive at -3.7 despite a 94% baseline, because the
tasks where it binds are exactly the ones where sorting was the right answer.

### What this design would have missed

Two of these checks judged the wrong function before this run. `_type_hints` and
`_single_return` took the *first* function defined rather than the one under test, and 1.5%
of submissions define a helper first - `kadane` above `max_sub_array_sum_repeated`. A model
that annotated exactly what it was asked to annotate would be scored as non-compliant
because its untyped scratch function came first. `single_return` also counted returns inside
nested helpers, and accepted a function with *no* return at all against a prompt asking for
exactly one.

## Running it

```bash
python run.py --limit 972
```

## Limits

- Compliance is checked syntactically. A model that satisfies the letter of "no imports" by
  inlining a library function counts as compliant.
- Six constraints on one benchmark. These are style rules, not the security or licensing
  constraints that would matter in production.
