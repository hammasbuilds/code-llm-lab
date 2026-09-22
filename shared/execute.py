"""Run a candidate solution against a task's tests, in a separate process with a timeout.

Shared by every project in this lab, because the thing that makes a code benchmark
reproducible is not the prompt - it is the execution rule. How code is extracted from a
model response and how it is run decides the score more than the model does.

Outcomes stay separated rather than collapsing into pass/fail:

- `pass`    - all tests held
- `fail`    - an assertion failed, the honest way to be wrong
- `error`   - any other exception
- `timeout` - did not finish

`fail` and `error` both count as rejected, but only `fail` means the tests actually tested
something. A candidate caught by crashing would have survived behind a guard clause.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 10.0

# Solution first, then setup, then tests. Setup sometimes instantiates classes the
# solution defines, so running it first raises NameError on perfectly good code.
_RUNNER = """\
import sys
{code}

{setup}

{tests}
print("__OK__")
"""

_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class Outcome:
    status: str
    detail: str = ""
    # The whole of stderr, not just its last line. `detail` is deliberately the last line
    # because most callers want a one-line label, but for an AssertionError that line is
    # the bare word "AssertionError" - no file, no line number, no source, no values.
    # A caller that wanted to show a model "what the tests printed" and reached for
    # `detail` was showing it fourteen characters, and project 13 did exactly that for
    # two runs while calling the arm `traceback`.
    stderr: str = ""
    # What the candidate printed, with the runner's own success marker removed. Needed by
    # anything that probes a program for a *value* rather than a verdict: such a probe
    # succeeds, and a successful Outcome carries no `detail` at all, so a caller reading
    # `detail` for the answer gets the empty string exactly when the answer exists.
    stdout: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    @property
    def traceback(self) -> str:
        """The real traceback, with the harness's own wrapper frame dropped.

        The runner writes solution, setup and asserts into one temporary file, so every
        traceback's first frame is that file rather than anything the model wrote. It is
        noise at best and misdirection at worst - it points at a path that does not exist
        on the reader's machine.
        """
        if not self.stderr:
            return self.detail
        lines = self.stderr.splitlines()
        kept = [ln for ln in lines if "candidate.py" not in ln]
        return "\n".join(kept).strip() or self.stderr.strip()


def extract_code(raw: str) -> str:
    """Pull code out of a model response.

    Permissive on purpose: a fenced block if there is one, otherwise the whole response.
    Stricter rules score the same generations far lower, and that variance is a property
    of the harness rather than of the model.
    """
    if not raw:
        return ""
    m = _FENCE.search(raw)
    return (m.group(1) if m else raw).strip()


def extract_solution(raw: str) -> str:
    """The block that defines something, when a response contains several.

    `extract_code` takes the **first** fenced block, which is right when the prompt asks for
    one. It is wrong whenever the prompt asks for code *before* the answer - "write the
    tests first, then the function" - because the first block is then the tests.

    That is not hypothetical. Project 17's `tests_then` arm scored 17.0% against 77.0% for
    answering directly, and the gap was entirely this: of 74 multi-block responses examined,
    **74** had asserts in the first block and the function in the last. The arm was marking
    the model's tests as its submission.

    So: the last fenced block that binds a name with `def` or `class`, falling back to the
    last block, falling back to the first code-looking line onwards. Single-block responses
    are unaffected, which keeps every arm that has only ever produced one block comparable
    with its earlier runs.

    Two cases the obvious version got wrong, both found by reading the failures rather than
    trusting the number:

    **An unterminated final fence.** The block regex needs a closing fence, so a response cut
    off mid-function yields only the *earlier* blocks - the tests. Eight of 200 `tests_then`
    responses ended that way, and each submitted its asserts. The text after a dangling
    opening fence is treated as a block.

    **No fence at all.** Returning the raw response then submits an essay, which fails to
    compile and reads as the model getting the task wrong. If there is a `def` in there, the
    code starts at the first import or definition.
    """
    if not raw:
        return ""
    blocks = [b.strip() for b in _FENCE.findall(raw) if b.strip()]

    # A dangling opening fence: everything after it is the block the model was still writing.
    tail = _FENCE.sub("", raw)
    if tail.count("```") % 2 == 1:
        remainder = tail.rsplit("```", 1)[1]
        remainder = re.sub(r"^(?:python|py)?[ \t]*\n", "", remainder, count=1)
        if remainder.strip():
            blocks.append(remainder.strip())

    if blocks:
        defining = [b for b in blocks if re.search(r"^\s*(def|class)\s", b, re.M)]
        return (defining or blocks)[-1]
    return _from_first_code_line(raw)


def _from_first_code_line(raw: str) -> str:
    """Everything from the first import or definition onwards, for an unfenced response."""
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*(def|class|import|from)\s", line):
            return "\n".join(lines[i:]).strip()
    return raw.strip()


def strip_self_tests(code: str) -> str:
    """Remove top-level `assert` statements from a submission.

    A prompt that asks for tests *and* an implementation often gets both in one fenced
    block, asserts first. Submitting the block whole then runs the model's own tests as part
    of the candidate - and they execute above the `def`, so a correct function fails with
    `NameError: name 'f' is not defined`. Where they do run, a wrong self-test rejects a
    right answer.

    Either way the model ends up marking its own homework, which is the one thing project 17
    is written to avoid. Only module-level asserts go: an assert inside a function is a guard
    clause the author meant to keep.
    """
    if "assert" not in code:
        return code
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    kept = [n for n in tree.body if not isinstance(n, ast.Assert)]
    if len(kept) == len(tree.body):
        return code
    if not kept:
        # Nothing but asserts. Returning "" is honest - there is no candidate here - and
        # far better than submitting the tests and calling the failure a wrong answer.
        return ""
    try:
        return ast.unparse(ast.Module(body=kept, type_ignores=[]))
    except (ValueError, RecursionError):
        return code


def run(code: str, tests, setup: str = "", timeout: float = TIMEOUT) -> Outcome:
    if isinstance(tests, str):
        tests = [tests]
    src = _RUNNER.format(code=code, setup=setup, tests="\n".join(tests))
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "candidate.py"
        # newline="" disables Windows LF->CRLF translation. Source that already contains
        # CRLF would otherwise become CR CR LF and break backslash line-continuations,
        # turning valid code into a SyntaxError.
        f.write_text(src, encoding="utf-8", newline="")
        try:
            r = subprocess.run(
                [sys.executable, str(f)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=tmp,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return Outcome("timeout")
        except OSError as exc:
            return Outcome("error", f"spawn failed: {exc}")

    out = (r.stdout or "").replace("__OK__", "").strip()
    if "__OK__" in (r.stdout or ""):
        return Outcome("pass", "", "", out)
    err = (r.stderr or "").strip()
    last = err.rsplit("\n", 1)[-1] if err else ""
    if "AssertionError" in err:
        return Outcome("fail", last, err, out)
    return Outcome("error", last[:200], err, out)


def run_many(jobs: list[tuple], workers: int = 6) -> list[Outcome]:
    """Each job is (code, tests, setup). Threads, since the work is in subprocesses."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda j: run(*j), jobs))
