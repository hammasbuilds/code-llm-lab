#!/usr/bin/env bash
# Resume from 06_temperature_pass_at_k. Everything before it is complete.
#
# Fourth restart. The previous three died with their owning session; this one died while
# running under Task Scheduler, which turned out to ship defaults that kill long jobs:
#
#   StopIfGoingOnBatteries      true
#   DisallowStartIfOnBatteries  true
#   StopOnIdleEnd               true
#
# Registered again with all three disabled and no execution time limit, plus restart-on-
# failure, so a single stall no longer ends the run.
set -u
LOG=/d/github/code-llm-lab/docs/expand.log
LAB=/d/github/code-llm-lab

run() {
  local name="$1"; shift
  # Skip anything already finished, so a restart after a stall costs nothing and a
  # re-registered task cannot redo completed work.
  if grep -q "^########## $name exit=0" "$LOG"; then
    echo "########## $name already complete, skipping $(date +%H:%M:%S)" >> "$LOG"
    return
  fi
  echo "########## $name $* $(date +%H:%M:%S)" >> "$LOG"
  (cd "$LAB" && .venv/Scripts/python.exe "projects/$name/run.py" "$@") >> "$LOG" 2>&1
  echo "########## $name exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

other() {
  local label="$1" dir="$2"; shift 2
  if grep -q "^########## $label exit=0" "$LOG"; then
    echo "########## $label already complete, skipping $(date +%H:%M:%S)" >> "$LOG"
    return
  fi
  echo "########## $label $(date +%H:%M:%S)" >> "$LOG"
  (cd "$dir" && "$@") >> "$LOG" 2>&1
  echo "########## $label exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

echo "########## RESUMED-5 (hardened task) $(date +%H:%M:%S)" >> "$LOG"

run 06_temperature_pass_at_k --limit 200
run 15_batch_vs_single       --limit 972
run 17_test_first            --limit 972
run 19_comment_injection     --limit 200
run 16_coder_vs_generalist   --limit 500
run 10_context_dilution      --limit 972
run 14_constraint_compliance --limit 972

other "sql-analyst-agent eval (retry)" /d/github/sql-analyst-agent \
  .venv/Scripts/python.exe -m sqlanalyst.cli eval
other "code-eval-harness 164 (retry)" /d/github/code-eval-harness \
  env PYTHONPATH=src "$LAB/.venv/Scripts/python.exe" src/run_eval.py 164

echo "EXPAND DONE $(date +%H:%M:%S)" >> "$LOG"
echo "ALL DONE $(date +%H:%M:%S)" >> "$LOG"
