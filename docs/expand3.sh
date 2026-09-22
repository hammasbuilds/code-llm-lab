#!/usr/bin/env bash
# Second resume of the lab expansion. expand2.sh died with the session that owned it,
# mid-way through 05's `docstring` arm - the same failure that killed expand.sh at 22:31.
#
# The difference this time: launched through a cmd batch + `start`, so the process is owned
# by cmd rather than by the session's bash and survives the session ending. That wrapper was
# applied to followon.sh but not to the lab queue itself, because expand2.sh was already
# running and inherited - a running script cannot be re-parented without killing it. The
# right move was to relaunch it detached at the first opportunity.
#
# Appends to the same expand.log, so `grep -q "EXPAND DONE"` in followon.sh still chains.
# Completed arms are cached, so 05 resumes through `plain` and most of `docstring` in
# seconds rather than re-generating them.
set -u
cd /d/github/code-llm-lab
LOG=docs/expand.log

run() {
  local name="$1"; shift
  echo "########## $name $* $(date +%H:%M:%S)" >> "$LOG"
  .venv/Scripts/python.exe "projects/$name/run.py" "$@" >> "$LOG" 2>&1
  echo "########## $name exit=$? $(date +%H:%M:%S)" >> "$LOG"
}

echo "########## RESUMED-2 $(date +%H:%M:%S)" >> "$LOG"

run 05_prompt_shape_variance --limit 972
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
