#!/usr/bin/env bash
# One ordered queue: finish 05, yield to another session's judge run, then shortest job first.
#
# `05_prompt_shape_variance` is deliberately NOT restarted here. Its python was left running
# and only its parent script was replaced, so the arm in flight is never interrupted - this
# waits for that process to exit before doing anything.
#
# After it: stand down so `01_faithful` (D:\standalone projects 14b_instruct) can finish its
# judge run at 366/600. Its own poller is already armed and starts itself the moment ollama
# reports a free card; we neither launch it nor touch its files. Its --max-wait is 12 hours,
# which this queue would have blown straight through.
#
# Then everything else, shortest estimate first, so the most results land soonest. The three
# non-lab jobs used to hang off followon.sh / followon2.sh; those are folded in here instead,
# and those two scripts are stopped, or the same jobs would run twice.
set -u
LOG=/d/github/code-llm-lab/docs/expand.log
JUDGE="/d/standalone projects 14b_instruct/01_faithful/data/judge_runs.jsonl"
LAB=/d/github/code-llm-lab

run() {
  local name="$1"; shift
  echo "########## $name $* $(date +%H:%M:%S)" >> "$LOG"
  (cd "$LAB" && .venv/Scripts/python.exe "projects/$name/run.py" "$@") >> "$LOG" 2>&1
  echo "########## $name exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

other() {  # a job in another repo: label, directory, then the command
  local label="$1" dir="$2"; shift 2
  echo "########## $label $(date +%H:%M:%S)" >> "$LOG"
  (cd "$dir" && "$@") >> "$LOG" 2>&1
  echo "########## $label exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

echo "########## REORDERED $(date +%H:%M:%S)" >> "$LOG"

# --- 1. let 05 finish, untouched -------------------------------------------------------
echo "########## waiting for 05 to finish $(date +%H:%M:%S)" >> "$LOG"
while ps -W 2>/dev/null | grep -q "code-llm-lab/.venv"; do sleep 60; done
echo "########## 05 finished $(date +%H:%M:%S)" >> "$LOG"

# --- 2. yield the card to the judge ----------------------------------------------------
echo "########## YIELDING to 01_faithful judge run $(date +%H:%M:%S)" >> "$LOG"
gone=0
for _ in $(seq 1 480); do
  lines=$(wc -l < "$JUDGE" 2>/dev/null || echo 0)
  if [ "$lines" -ge 600 ]; then
    echo "########## judge reached $lines/600 $(date +%H:%M:%S)" >> "$LOG"; break
  fi
  if ps -W 2>/dev/null | grep -q "14b_instruct"; then gone=0; else gone=$((gone + 1)); fi
  if [ "$gone" -ge 5 ]; then
    echo "########## 01_faithful not running, at $lines/600 - resuming $(date +%H:%M:%S)" >> "$LOG"
    break
  fi
  sleep 120
done

# --- 3. everything else, shortest first ------------------------------------------------
other "sql-analyst-agent eval"       /d/github/sql-analyst-agent    .venv/Scripts/python.exe -m sqlanalyst.cli evaluate
other "code-eval-harness 164"        /d/github/code-eval-harness    env PYTHONPATH=src .venv/Scripts/python.exe src/run_eval.py 164
other "mbpp-false-accepts humaneval" /d/github/mbpp-false-accepts   "$LAB/.venv/Scripts/python.exe" run_model.py --split humaneval

run 07_docstring_roundtrip   --limit 972
run 02_self_debug_ceiling    --limit 500
run 03_tests_that_kill       --limit 500
run 18_determinism           --limit 400 --runs 5
run 06_temperature_pass_at_k --limit 200
run 15_batch_vs_single       --limit 972
run 17_test_first            --limit 972
run 19_comment_injection     --limit 200
run 16_coder_vs_generalist   --limit 500
run 10_context_dilution      --limit 972
run 14_constraint_compliance --limit 972

echo "EXPAND DONE $(date +%H:%M:%S)" >> "$LOG"
echo "ALL DONE $(date +%H:%M:%S)" >> "$LOG"
