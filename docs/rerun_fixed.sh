#!/usr/bin/env bash
# Re-measure the two out-of-queue projects whose repair prompt was handed
# "Running the tests gave: AssertionError" and nothing else.
#
# `Outcome.detail` is stderr's LAST LINE, which for an AssertionError is the bare word
# AssertionError - no file, no line, no source, no values. Three projects fed that into a
# model as if it were an error message. 02 is in the lab queue and will pick the fix up
# when it gets there; 13 is already running; 04 is chained here behind it.
#
# 04 matters most of the three. Its finding is "repair and rewrite are indistinguishable",
# and a broken error message handicaps only the repair arm - rewrite never reads it. The
# comparison was not fair, so the negative result does not stand until this run lands.
set -u
cd /d/github/code-llm-lab
LOG=docs/rerun_fixed.log
: > "$LOG"
PY=.venv/Scripts/python.exe

# Wait for project 13, but not forever: if it died with its launching session, 04 should
# still run rather than the chain stalling silently until morning.
echo "waiting for project 13 $(date +%H:%M:%S)" >> "$LOG"
for _ in $(seq 1 80); do
  grep -q "wrote " docs/p13_rerun.log 2>/dev/null && break
  sleep 30
done
if grep -q "wrote " docs/p13_rerun.log 2>/dev/null; then
  echo "project 13 finished $(date +%H:%M:%S)" >> "$LOG"
else
  echo "project 13 did not finish in 40m - running 04 anyway $(date +%H:%M:%S)" >> "$LOG"
fi

echo "########## 04_repair_vs_rewrite --limit 972 $(date +%H:%M:%S)" >> "$LOG"
"$PY" projects/04_repair_vs_rewrite/run.py --limit 972 --workers 6 >> "$LOG" 2>&1
echo "########## 04_repair_vs_rewrite exit=$? $(date +%H:%M:%S)" >> "$LOG"

echo "RERUN FIXED DONE $(date +%H:%M:%S)" >> "$LOG"
