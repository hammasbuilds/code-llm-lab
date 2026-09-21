"""First-attempt solutions, generated once and shared by every project that needs them.

Projects 08 and 11 both start from "a solution this model wrote", which project 01 already
generated for 250 MBPP tasks. The generation cache is keyed on
`(model, prompt, temperature, seed)`, so asking the same question the same way costs
nothing - but only if the prompt is byte-identical. Copying the template into each project
is how that silently stops being true.

So the template lives here, and `solve()` is the one way to ask.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.datasets import Task
from shared.execute import Outcome, extract_code, run_many
from shared.model import generate_many

# Byte-identical to projects/01_coder_size_curve/run.py. Do not reword: a changed character
# is a full cache miss and 250 fresh generations.
MBPP_PROMPT = """Write a Python function for this task.

Task: {prompt}

It must satisfy this test:
{test}

Output ONLY the function definition and any imports it needs. No explanation, no tests.
"""

HUMANEVAL_PROMPT = """Complete this Python function.

{prompt}

Output ONLY the complete function including its signature. No explanation, no tests.
"""


def build_prompt(task: Task) -> str:
    if task.is_mbpp:
        return MBPP_PROMPT.format(prompt=task.prompt, test=task.tests[0])
    return HUMANEVAL_PROMPT.format(prompt=task.prompt)


@dataclass(frozen=True)
class Solution:
    task: Task
    code: str
    outcome: Outcome

    @property
    def passed(self) -> bool:
        return self.outcome.passed


def solve(
    tasks: list[Task],
    model: str = "qwen2.5-coder:14b",
    workers: int = 8,
    progress: str = "solve",
) -> list[Solution]:
    """Generate one solution per task and run it against that task's own tests."""
    raws = generate_many(
        [build_prompt(t) for t in tasks],
        model=model,
        temperature=0.0,
        workers=workers,
        progress=progress,
    )
    codes = [extract_code(r) if r else "" for r in raws]
    outcomes = run_many(
        [(c, list(t.tests), t.setup) for c, t in zip(codes, tasks, strict=True)],
        workers,
    )
    return [
        Solution(task=t, code=c, outcome=o) for t, c, o in zip(tasks, codes, outcomes, strict=True)
    ]
