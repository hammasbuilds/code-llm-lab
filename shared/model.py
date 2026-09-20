"""Talk to Ollama over plain HTTP, with an on-disk cache.

Every project here re-asks the same model the same questions, so generations are cached
by (model, prompt, temperature, seed). A project that is re-run, extended or interrupted
pays for generation once. That matters when a sweep is 974 problems x 5 settings.

`urllib` only - the whole lab has no runtime dependencies beyond pandas for one parquet.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA = "http://localhost:11434"
CACHE = Path(__file__).resolve().parent.parent / "cache"
_LOCK = threading.Lock()


def _key(model: str, prompt: str, temperature: float, seed: int | None) -> str:
    h = hashlib.sha256(
        json.dumps([model, prompt, temperature, seed], sort_keys=True).encode()
    ).hexdigest()
    return h[:40]


def generate(
    prompt: str,
    model: str = "qwen2.5-coder:14b",
    temperature: float = 0.0,
    seed: int | None = None,
    num_predict: int = 512,
    timeout: int = 240,
    use_cache: bool = True,
) -> str | None:
    """One completion. Returns None only if the model could not be reached."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / f"{_key(model, prompt, temperature, seed)}.json"
    if use_cache and cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))["response"]
        except (json.JSONDecodeError, KeyError):
            pass  # a truncated cache entry is worth less than a re-request

    options: dict = {"temperature": temperature, "num_predict": num_predict}
    if seed is not None:
        options["seed"] = seed
    payload = {"model": model, "prompt": prompt, "stream": False, "options": options}
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            text = json.loads(fh.read()).get("response", "")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    if use_cache:
        with _LOCK:
            cache_file.write_text(
                json.dumps(
                    {
                        "model": model,
                        "temperature": temperature,
                        "seed": seed,
                        "prompt": prompt,
                        "response": text,
                    }
                ),
                encoding="utf-8",
            )
    return text


def available(model: str) -> bool:
    try:
        r = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=30, check=False
        )
        return model.split(":")[0] in r.stdout and model.split(":")[-1] in r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def cache_size() -> int:
    return len(list(CACHE.glob("*.json"))) if CACHE.exists() else 0
