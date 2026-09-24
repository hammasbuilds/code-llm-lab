#!/usr/bin/env bash
# Round two. Each job targets a specific weakness in one of the four repos, not more data
# for its own sake.
#
#   sql-analyst-agent   ran its whole eval on qwen2.5:3b-instruct and scored 40% accuracy
#                       while a 14B coder sat on the same card. Rerun on the 14B.
#
#   mbpp-false-accepts  the mutation arm now has three suite sizes (3 asserts / 7.2 / 775
#                       EvalPlus cases). The model arm has only two. This adds the third.
#
#   code-eval-harness   its headline is "same generations, 0% or 85%, depending on the
#                       extraction rule" - but all three fence rules agree on all 492
#                       records, because this model emits clean fences. The finding needs
#                       models that do not: smaller ones, and a non-zero temperature.
#
#   code-llm-lab        16's finding reversed between 250 and 500 tasks. The honest question
#                       a reader then asks is which of the other nineteen would also flip.
#                       18_determinism answers it for the base generations at one seed; this
#                       runs it at three more, so the replication claim rests on four.
set -u
LOG=/d/github/code-llm-lab/docs/upgrade.log
LAB=/d/github/code-llm-lab
: > "$LOG"

run() {
  local label="$1" dir="$2"; shift 2
  if grep -q "^########## $label exit=0" "$LOG" 2>/dev/null; then
    echo "########## $label already complete, skipping $(date +%H:%M:%S)" >> "$LOG"; return
  fi
  echo "########## $label $(date +%H:%M:%S)" >> "$LOG"
  (cd "$dir" && "$@") >> "$LOG" 2>&1
  echo "########## $label exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

# 1. cheapest and biggest single improvement: 3B -> 14B on 47 questions
run "sql-analyst-agent on 14b" /d/github/sql-analyst-agent \
  .venv/Scripts/python.exe -m sqlanalyst.cli eval

# 2. completes the suite-size curve in the model arm
run "mbpp-false-accepts humanevalplus" /d/github/mbpp-false-accepts \
  "$LAB/.venv/Scripts/python.exe" run_model.py --split humanevalplus

# 3. extraction rules only differ on messy output; these models produce it
run "code-eval-harness messy models" /d/github/code-eval-harness \
  env PYTHONPATH=src "$LAB/.venv/Scripts/python.exe" src/run_eval.py 164 \
  --models granite3.3:2b,llama3.2:3b,qwen2.5:3b-instruct

# 4. replication: the same 400 tasks, three more seeds
run "18_determinism seeds 6-8" "$LAB" \
  .venv/Scripts/python.exe projects/18_determinism/run.py --limit 400 --runs 8

echo "UPGRADE DONE $(date +%H:%M:%S)" >> "$LOG"
