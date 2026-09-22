#!/usr/bin/env bash
# The lab expansion, with a deliberate yield after 05 so another session's last job can run.
#
# `01_faithful` (D:\standalone projects 14b_instruct) has a judge run stopped at 366/600. Its
# own `scripts/gpu_queue.py` is already armed and polling: it waits until the card is free or
# already holds its model, and it never evicts anyone. That is the right design and it does
# not need help from us.
#
# What it does need is a gap. Its `--max-wait` is 12 hours, and this queue has eleven jobs
# left at roughly two hours each - so it would poll politely for twelve hours, give up with
# exit 2, and that session's last task would never finish. Not because anything went wrong,
# but because we never stopped holding the card.
#
# So: finish 05, then stand down until the judge reaches 600 (or its process goes away), then
# carry on. We do not start their run, touch their files, or kill anything of theirs - their
# queue starts itself the moment ollama reports the card free.
set -u
cd /d/github/code-llm-lab
LOG=docs/expand.log
JUDGE="/d/standalone projects 14b_instruct/01_faithful/data/judge_runs.jsonl"

run() {
  local name="$1"; shift
  echo "########## $name $* $(date +%H:%M:%S)" >> "$LOG"
  .venv/Scripts/python.exe "projects/$name/run.py" "$@" >> "$LOG" 2>&1
  echo "########## $name exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

echo "########## RESUMED-3 $(date +%H:%M:%S)" >> "$LOG"

run 05_prompt_shape_variance --limit 972

# --- yield the card to 01_faithful -----------------------------------------------------
# Nothing here is requested from ollama, so our model falls out of VRAM when its keep_alive
# expires and their poller sees a free card within a minute or so.
echo "########## YIELDING to 01_faithful judge run $(date +%H:%M:%S)" >> "$LOG"
gone=0
for _ in $(seq 1 480); do          # 16 hours at 2 min, well past their own 12h give-up
  lines=$(wc -l < "$JUDGE" 2>/dev/null || echo 0)
  if [ "$lines" -ge 600 ]; then
    echo "########## judge reached $lines/600 $(date +%H:%M:%S)" >> "$LOG"
    break
  fi
  # If their process disappears and stays gone, it either finished short or gave up; either
  # way continuing to hold the card back helps nobody.
  if ps -W 2>/dev/null | grep -q "14b_instruct"; then gone=0; else gone=$((gone + 1)); fi
  if [ "$gone" -ge 5 ]; then
    echo "########## 01_faithful not running, at $lines/600 - resuming $(date +%H:%M:%S)" >> "$LOG"
    break
  fi
  sleep 120
done

run 07_docstring_roundtrip   --limit 972
run 14_constraint_compliance --limit 972
run 15_batch_vs_single       --limit 972
run 10_context_dilution      --limit 972
run 02_self_debug_ceiling    --limit 500
run 17_test_first            --limit 972
run 03_tests_that_kill       --limit 500
run 18_determinism           --limit 400 --runs 5
run 06_temperature_pass_at_k --limit 200
run 19_comment_injection     --limit 200
run 16_coder_vs_generalist   --limit 500

echo "EXPAND DONE $(date +%H:%M:%S)" >> "$LOG"
