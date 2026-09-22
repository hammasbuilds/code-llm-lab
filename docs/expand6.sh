#!/usr/bin/env bash
# Resume from 18_determinism. Everything before it is complete.
#
# Third restart. `nohup` died with the session, and the `cmd /c start` wrapper died too -
# closing the terminal takes the whole console tree with it, so a "detached" bash that still
# owns a console is not actually detached. This script is therefore registered with Windows
# Task Scheduler instead, which runs it outside any console.
#
# 18_determinism started at 19:38:41 and wrote no progress at all before dying, so it is
# re-run from the top rather than resumed; its generations are cached either way.
set -u
LOG=/d/github/code-llm-lab/docs/expand.log
LAB=/d/github/code-llm-lab

run() {
  local name="$1"; shift
  echo "########## $name $* $(date +%H:%M:%S)" >> "$LOG"
  (cd "$LAB" && .venv/Scripts/python.exe "projects/$name/run.py" "$@") >> "$LOG" 2>&1
  echo "########## $name exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

other() {
  local label="$1" dir="$2"; shift 2
  echo "########## $label $(date +%H:%M:%S)" >> "$LOG"
  (cd "$dir" && "$@") >> "$LOG" 2>&1
  echo "########## $label exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

echo "########## RESUMED-4 (task scheduler) $(date +%H:%M:%S)" >> "$LOG"

run 18_determinism           --limit 400 --runs 5
run 06_temperature_pass_at_k --limit 200
run 15_batch_vs_single       --limit 972
run 17_test_first            --limit 972
run 19_comment_injection     --limit 200
run 16_coder_vs_generalist   --limit 500
run 10_context_dilution      --limit 972
run 14_constraint_compliance --limit 972

# The two that failed in seconds on commands that had never been executed before.
other "sql-analyst-agent eval (retry)" /d/github/sql-analyst-agent \
  .venv/Scripts/python.exe -m sqlanalyst.cli eval
other "code-eval-harness 164 (retry)" /d/github/code-eval-harness \
  env PYTHONPATH=src "$LAB/.venv/Scripts/python.exe" src/run_eval.py 164

echo "EXPAND DONE $(date +%H:%M:%S)" >> "$LOG"
echo "ALL DONE $(date +%H:%M:%S)" >> "$LOG"
