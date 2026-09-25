#!/usr/bin/env bash
# Restart the lab queue whenever it is not running. Scheduled every 10 minutes.
#
# The queue has now died five times from at least three different causes: a session ending
# (nohup, then the cmd/start wrapper), Task Scheduler's battery and idle defaults, and once
# cleanly mid-job with "Last Result: 0" and no exit line written. Diagnosing each new cause
# costs more GPU-hours than it saves, and the next one will be different again.
#
# So stop trying to make one process immortal. `expand7.sh` skips anything already marked
# exit=0, so restarting it is free and idempotent - which makes "just start it again" a
# complete answer to every cause at once, including ones not yet seen.
set -u
LOG=${1:-/d/github/code-llm-lab/docs/expand.log}
TASK=${2:-labqueue}
WLOG=/d/github/code-llm-lab/docs/watchdog.log

[ -f "$LOG" ] || exit 0

# Finished: nothing to guard.
if grep -q "ALL DONE\|UPGRADE2 DONE\|DET8 DONE" "$LOG"; then
  exit 0
fi

# Still working: leave it alone. The jobs in these queues run under three different
# virtualenvs - the lab's, sql-analyst-agent's, and code-eval-harness borrowing the lab's -
# so watching only for the lab's would call a running sql-analyst eval "stopped".
if ps -W 2>/dev/null | grep -qE "code-llm-lab/\.venv|sql-analyst-agent/\.venv|mbpp-false-accepts"; then
  exit 0
fi

# Do not fight another session for the card. If ollama is holding a model this queue did
# not ask for, that is somebody else's run and it gets to finish.
resident=$(curl -s -m 10 http://localhost:11434/api/ps 2>/dev/null)
if echo "$resident" | grep -q '"name"' && ! echo "$resident" | grep -q "qwen2.5-coder:14b"; then
  echo "$(date '+%F %H:%M:%S')  card held by another run, not restarting" >> "$WLOG"
  exit 0
fi

echo "$(date '+%F %H:%M:%S')  $TASK not running - restarting" >> "$WLOG"
# Trigger the `labqueue` task rather than spawning a child. Task Scheduler kills a task's
# whole process tree the moment the task's own process exits, so a `nohup ... &` from here
# dies within seconds of this script returning - which is the same reason every earlier
# attempt to detach the queue failed. A separate task has its own lifetime.
schtasks //run //tn "$TASK" >> "$WLOG" 2>&1
exit 0
