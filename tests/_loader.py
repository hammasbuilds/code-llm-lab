"""Import a project's `run.py` under a unique module name.

Every project has a file called `run.py`. The obvious way to reach one from a test is to
put its directory on `sys.path` and `import run` - but `sys.modules` is keyed by module
*name*, so the second project imported that way returns the first project's module, and
the test passes while asserting against the wrong file. Project directories also start
with a digit, so they are not importable as packages.

Loading each one from its path under a distinct name avoids both.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
_loaded: dict[str, ModuleType] = {}


def project(name: str) -> ModuleType:
    """`project("05_prompt_shape_variance")` -> that project's run.py, as a module."""
    if name in _loaded:
        return _loaded[name]

    path = ROOT / "projects" / name / "run.py"
    if not path.is_file():
        raise FileNotFoundError(path)

    # run.py does `sys.path.insert(0, parents[2])` to reach `shared`, which works whether
    # it is run as a script or loaded here.
    spec = importlib.util.spec_from_file_location(f"project_{name}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _loaded[name] = mod
    return mod
