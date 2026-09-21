#!/usr/bin/env bash
# Re-run the lab on the full MBPP corpus (972 tasks) instead of the convenience cuts.
#
# Ordered by where the small sample most undermines the finding, not by project number:
#
#   04 and 13 rest on 60 first-attempt failures and report differences of 1 vs 3 and 6 vs 1
#   tasks. At 972 they get ~230 failures, which is the difference between a number and an
#   anecdote. They run first.
#
#   01 comes next because seven projects reuse its base solution generations through the
#   shared prompt, so paying for it once unlocks 08, 11, 13, 16, 18 and 20.
#
#   The arms that cost a full generation pass per task (18 bypasses the cache, 19 has
#   thirteen arms, 16 has five models) are capped below 972 and the cap is recorded in the
#   result, because a number that never finishes is worth less than a smaller honest one.
#
# Measured throughput on this machine: 11.1 s/task for qwen2.5-coder:14b at 6 workers.
set -u
cd /d/github/code-llm-lab
LOG=docs/expand.log
: > "$LOG"

run() {
  local name="$1"; shift
  echo "########## $name $* $(date +%H:%M:%S)" >> "$LOG"
  .venv/Scripts/python.exe "projects/$name/run.py" "$@" >> "$LOG" 2>&1
  echo "########## $name exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

# --- the two weakest denominators in the repo ---------------------------------------
run 13_feedback_content   --limit 972
run 04_repair_vs_rewrite  --limit 972

# --- the shared base, which the rest reuse ------------------------------------------
run 01_coder_size_curve   --limit 972

# --- everything that reuses it, now nearly free -------------------------------------
run 08_review_false_alarms --limit 972
run 11_refactor_safety     --limit 972
run 20_feature_regression  --limit 972
run 09_confidence_gating   --limit 972

# --- own generations, one arm each ---------------------------------------------------
run 05_prompt_shape_variance --limit 972
run 07_docstring_roundtrip   --limit 972
run 14_constraint_compliance --limit 972
run 15_batch_vs_single       --limit 972
run 10_context_dilution      --limit 972
run 02_self_debug_ceiling    --limit 500
run 17_test_first            --limit 972
run 03_tests_that_kill       --limit 500

# --- capped: every arm is a full uncached pass ---------------------------------------
run 18_determinism         --limit 400 --runs 5
run 06_temperature_pass_at_k --limit 200
run 19_comment_injection   --limit 200
run 16_coder_vs_generalist --limit 500

echo "EXPAND DONE $(date +%H:%M:%S)" >> "$LOG"
