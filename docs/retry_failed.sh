#!/usr/bin/env bash
# The two non-lab jobs that failed immediately, with the commands corrected.
#
# Both were inherited verbatim from a followon.sh that was written but never actually
# reached, so neither command had ever been executed. They failed in under two seconds:
#
#   sql-analyst-agent   exit 2    the CLI command is `eval`, not `evaluate`
#   code-eval-harness   exit 127  that repo has no .venv at all
#
# code-eval-harness only needs pandas and pyarrow, both of which the lab venv already has,
# and `import run_eval` succeeds under it - so it runs on that interpreter rather than
# creating a second environment for two libraries.
#
# Chained behind the lab queue rather than run now, because 07 currently holds the card and
# starting these alongside it would just make both slower.
set -u
LOG=/d/github/code-llm-lab/docs/expand.log
LAB=/d/github/code-llm-lab

echo "########## retry_failed armed, waiting for the lab queue $(date +%H:%M:%S)" >> "$LOG"
while ! grep -q "ALL DONE" "$LOG"; do sleep 120; done

other() {
  local label="$1" dir="$2"; shift 2
  echo "########## $label $(date +%H:%M:%S)" >> "$LOG"
  (cd "$dir" && "$@") >> "$LOG" 2>&1
  echo "########## $label exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

other "sql-analyst-agent eval (retry)" /d/github/sql-analyst-agent \
  .venv/Scripts/python.exe -m sqlanalyst.cli eval

other "code-eval-harness 164 (retry)" /d/github/code-eval-harness \
  env PYTHONPATH=src "$LAB/.venv/Scripts/python.exe" src/run_eval.py 164

echo "RETRY DONE $(date +%H:%M:%S)" >> "$LOG"
