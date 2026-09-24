#!/usr/bin/env bash
# The two round-two jobs that failed on their first attempt, corrected.
#
#   sql-analyst-agent   reran on qwen2.5:3b-instruct despite the code default being changed
#                       to the 14B coder. The repo has a .env, and pydantic-settings ranks
#                       a .env file above a field default - so editing config.py changed
#                       nothing. An environment variable outranks both, and that is set
#                       here rather than editing a file that may hold credentials.
#
#   mbpp-false-accepts  --split humanevalplus was added to run_mutation.py and not to
#                       run_model.py, so the model arm rejected it in two seconds.
#
# Chained behind the first upgrade rather than run beside it; both want the same card.
set -u
LOG=/d/github/code-llm-lab/docs/upgrade.log
LAB=/d/github/code-llm-lab

echo "########## upgrade2 armed, waiting $(date +%H:%M:%S)" >> "$LOG"
while ! grep -q "UPGRADE DONE" "$LOG"; do sleep 60; done

run() {
  local label="$1" dir="$2"; shift 2
  echo "########## $label $(date +%H:%M:%S)" >> "$LOG"
  (cd "$dir" && "$@") >> "$LOG" 2>&1
  echo "########## $label exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

run "sql-analyst-agent on 14b (retry)" /d/github/sql-analyst-agent \
  env OLLAMA_MODEL=qwen2.5-coder:14b .venv/Scripts/python.exe -m sqlanalyst.cli eval

run "mbpp-false-accepts humanevalplus (retry)" /d/github/mbpp-false-accepts \
  "$LAB/.venv/Scripts/python.exe" run_model.py --split humanevalplus

echo "UPGRADE2 DONE $(date +%H:%M:%S)" >> "$LOG"
