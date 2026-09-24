#!/usr/bin/env bash
# Everything still outstanding from round two, in one script with skip-if-done.
#
# The previous two upgrade scripts died with the session that started them - the same
# failure as the main queue, and avoidable, because a watchdog had already been written
# for exactly this and was pointed only at `labqueue`. It now covers this too.
set -u
LOG=/d/github/code-llm-lab/docs/upgrade.log
LAB=/d/github/code-llm-lab

run() {
  local label="$1" dir="$2"; shift 2
  if grep -q "^########## $label exit=0" "$LOG" 2>/dev/null; then
    echo "########## $label already complete, skipping $(date +%H:%M:%S)" >> "$LOG"; return
  fi
  echo "########## $label $(date +%H:%M:%S)" >> "$LOG"
  (cd "$dir" && "$@") >> "$LOG" 2>&1
  echo "########## $label exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

echo "########## UPGRADE RESUMED $(date +%H:%M:%S)" >> "$LOG"

# The 14B model and the refusal fix both land in this run.
# Needs Postgres on 5434, from this repo's own compose file. It has failed twice with a
# connection timeout purely because Docker Desktop was not running after a reboot - which
# reads like a bug in the agent rather than a container that is not up. Start the database
# first, wait for healthy, and only then run the eval.
ensure_postgres() {
  if ! docker version >/dev/null 2>&1; then
    echo "########## starting Docker Desktop $(date +%H:%M:%S)" >> "$LOG"
    cmd //c start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" >/dev/null 2>&1
    for _ in $(seq 1 60); do docker version >/dev/null 2>&1 && break; sleep 10; done
  fi
  docker version >/dev/null 2>&1 || return 1
  (cd /d/github/sql-analyst-agent && docker compose up -d) >> "$LOG" 2>&1
  for _ in $(seq 1 30); do
    docker ps --filter name=sqlanalyst-postgres --format "{{.Status}}" 2>/dev/null | grep -q healthy && return 0
    sleep 5
  done
  return 1
}

if ensure_postgres; then
  run "sql-analyst-agent 14b fixed" /d/github/sql-analyst-agent \
    env OLLAMA_MODEL=qwen2.5-coder:14b .venv/Scripts/python.exe -m sqlanalyst.cli eval
else
  echo "########## sql-analyst skipped: no postgres on 5434 $(date +%H:%M:%S)" >> "$LOG"
fi

# Completes the suite-size curve in the model arm; --split humanevalplus now exists there.
run "mbpp-false-accepts humanevalplus fixed" /d/github/mbpp-false-accepts \
  "$LAB/.venv/Scripts/python.exe" run_model.py --split humanevalplus

# Replication: the same 400 tasks at eight seeds instead of five.
run "18_determinism 8 runs" "$LAB" \
  .venv/Scripts/python.exe projects/18_determinism/run.py --limit 400 --runs 8

# The coder model emits clean fences, so all three fence rules agreed on all 492
# records and the comparison had nothing to compare. qwen2.5:14b-instruct is the
# right second model: same size, same family, but tuned to explain itself - which is
# exactly the output an extraction rule has to survive.
# Re-queued: the first attempt passed a stray `--models` flag, so the model name was
# literally "--models", all 492 generations returned HTTPError, and the job still exited 0
# with an empty table. run_eval.py now refuses to do that; the label is changed so the
# skip-if-done check does not match the bogus success.
run "code-eval-harness messy models v2" /d/github/code-eval-harness   env PYTHONPATH=src "$LAB/.venv/Scripts/python.exe" src/run_eval.py 164   qwen2.5-coder:14b,qwen2.5:14b-instruct

echo "UPGRADE DONE $(date +%H:%M:%S)" >> "$LOG"
echo "UPGRADE2 DONE $(date +%H:%M:%S)" >> "$LOG"
