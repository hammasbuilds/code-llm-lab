#!/usr/bin/env bash
# Resume the full-MBPP expansion. The first five landed before the previous session's
# process exited and took the queue with it; this picks up from where that stopped.
set -u
cd /d/github/code-llm-lab
LOG=docs/expand.log

run() {
  local name="$1"; shift
  echo "########## $name $* $(date +%H:%M:%S)" >> "$LOG"
  .venv/Scripts/python.exe "projects/$name/run.py" "$@" >> "$LOG" 2>&1
  echo "########## $name exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

echo "########## RESUMED $(date +%H:%M:%S)" >> "$LOG"

run 20_feature_regression  --limit 972
run 09_confidence_gating   --limit 972
run 05_prompt_shape_variance --limit 972
run 07_docstring_roundtrip   --limit 972
run 14_constraint_compliance --limit 972
run 15_batch_vs_single       --limit 972
run 10_context_dilution      --limit 972
run 02_self_debug_ceiling    --limit 500
run 17_test_first            --limit 972
run 03_tests_that_kill       --limit 500
run 18_determinism         --limit 400 --runs 5
run 06_temperature_pass_at_k --limit 200
run 19_comment_injection   --limit 200
run 16_coder_vs_generalist --limit 500

echo "EXPAND DONE $(date +%H:%M:%S)" >> "$LOG"
