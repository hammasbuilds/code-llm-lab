#!/usr/bin/env bash
# 18_determinism, eight clean runs.
#
# The first 8-run attempt was wrecked by VRAM contention: three of its eight runs overlapped
# another session's 14B sharing the card, requests timed out, and lost generations scored as
# wrong answers. It reported 31.8% of tasks flipping verdict at temperature 0 when the five
# unaffected runs agreed to within 0.2 points.
#
# Two guards now. run.py raises if a run loses more than 2% of its generations, so the same
# failure cannot be scored again. And this waits for an empty card before starting, rather
# than loading a second 14B beside somebody else's.
set -u
LOG=/d/github/code-llm-lab/docs/det8.log
LAB=/d/github/code-llm-lab

grep -q "DET8 DONE" "$LOG" 2>/dev/null && exit 0

# Wait for the card. Not "holds my model" - empty. Two 14Bs in 16 GB is the failure being
# guarded against, and the other session's model is as much a problem as a stale copy of mine.
for _ in $(seq 1 180); do
  n=$(curl -s -m 10 http://localhost:11434/api/ps 2>/dev/null | grep -c '"name"')
  [ "${n:-1}" -eq 0 ] && break
  echo "$(date '+%F %H:%M:%S')  card holds $n model(s), waiting" >> "$LOG"
  sleep 60
done

echo "########## 18_determinism 8 clean runs $(date +%H:%M:%S)" >> "$LOG"
(cd "$LAB" && .venv/Scripts/python.exe projects/18_determinism/run.py --limit 400 --runs 8) >> "$LOG" 2>&1
echo "########## exit=$? $(date +%H:%M:%S)" >> "$LOG"
echo "DET8 DONE $(date +%H:%M:%S)" >> "$LOG"
