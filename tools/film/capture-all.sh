#!/bin/bash
# Captures every frame of a film plan batch by batch (managed-browser scripts are leased ~110 s), and
# refuses to stall: every CLI call has a hard timeout, a batch that makes no progress triggers
# recovery (runtime recover, then a headless dev restart), black frames (e.g. a stuck XR session
# leaving the renderer presenting) are deleted and recaptured after a restart, and the whole run has
# a deadline. It exits non-zero with a reason instead of looping forever.
# Usage: tools/film/capture-all.sh <plan.json> <out_dir>
# Env: FILM_MAX_MINUTES (default 40), FILM_MAX_RECOVERIES (default 4), FILM_NO_RELOAD=1 to skip the
# initial page reload (by default the page is reloaded so the current model and assets are captured)
PLAN=$1; OUT=$2; NEXT=0
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1
MAX_MIN=${FILM_MAX_MINUTES:-40}; MAX_REC=${FILM_MAX_RECOVERIES:-4}
DEADLINE=$(( $(date +%s) + MAX_MIN * 60 ))
TOTAL=$(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))['frames']))" "$PLAN") || exit 1
log() { echo "[$(date +%H:%M:%S)] $*"; }
# portable hard timeout (macOS has no coreutils timeout): perl alarm, then exec
run_for() { local secs=$1; shift; perl -e 'alarm shift; exec @ARGV' "$secs" "$@"; }
ready() { run_for 30 npx @iwsdk/cli dev status 2>/dev/null | grep -q '"browserCommandReady": true'; }
recover() {
  local level=$1
  if [ "$level" -le 1 ]; then
    log "recovery: runtime recover"
    run_for 120 npx @iwsdk/cli runtime recover --timeout 90000 >/dev/null 2>&1
  else
    log "recovery: headless dev restart"
    run_for 180 npx @iwsdk/cli dev restart --headless --allow-browser-automation --timeout 120000 >/dev/null 2>&1
  fi
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do ready && { log "browser ready"; return 0; }; sleep 5; done
  log "browser still not ready after recovery"; return 1
}
# first black frame (mean luminance < 2) in [from, to), or -1
first_black() {
  python3 - "$OUT" "$1" "$2" <<'EOF'
import sys, os
from PIL import Image, ImageStat
out, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
for i in range(a, b):
    p = os.path.join(out, f'f{i:05d}.png')
    if os.path.exists(p) and ImageStat.Stat(Image.open(p).convert('L').resize((96, 54))).mean[0] < 2:
        print(i); break
else:
    print(-1)
EOF
}
FAILS=0; RECOVERIES=0
ready || recover 1 || recover 2 || { log "managed browser unavailable"; exit 2; }
# always capture the current build: a model or asset exported since the page loaded is otherwise cached
if [ -z "$FILM_NO_RELOAD" ]; then
  log "reloading the page"
  run_for 60 npx @iwsdk/cli browser reload >/dev/null 2>&1 || run_for 60 npx @iwsdk/cli browser reload >/dev/null 2>&1
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do ready && break; sleep 5; done
fi
while [ "$NEXT" -lt "$TOTAL" ]; do
  if [ "$(date +%s)" -gt "$DEADLINE" ]; then log "deadline of $MAX_MIN min reached at $NEXT / $TOTAL"; exit 3; fi
  R=$(FILM_PLAN=$PLAN FILM_OUT=$OUT FILM_START=$NEXT FILM_COUNT=400 FILM_BUDGET_MS=95000 \
      run_for 130 npx @iwsdk/cli browser run tools/film/capture-frames.mjs --timeout 110000 2>&1)
  N=$(echo "$R" | grep -o '"next": [0-9]*' | grep -o '[0-9]*$')
  if [ -n "$N" ] && [ "$N" -gt "$NEXT" ]; then
    B=$(first_black "$NEXT" "$N")
    if [ "$B" -ge 0 ] 2>/dev/null; then
      log "black frames from $B: deleting and recapturing after a restart"
      for ((i = B; i < N; i++)); do rm -f "$(printf '%s/f%05d.png' "$OUT" "$i")"; done
      NEXT=$B; RECOVERIES=$((RECOVERIES + 1))
      [ "$RECOVERIES" -gt "$MAX_REC" ] && { log "gave up after $MAX_REC recoveries at $NEXT / $TOTAL"; exit 4; }
      recover 2 || { log "restart failed at $NEXT / $TOTAL"; exit 2; }
      FAILS=0; continue
    else
      NEXT=$N; FAILS=0; log "captured up to $NEXT / $TOTAL"; continue
    fi
  else
    FAILS=$((FAILS + 1)); log "no progress at $NEXT (attempt $FAILS): $(echo "$R" | grep -o '"message": "[^"]*"' | head -1)"
  fi
  if [ "$FAILS" -ge 2 ]; then
    RECOVERIES=$((RECOVERIES + 1))
    [ "$RECOVERIES" -gt "$MAX_REC" ] && { log "gave up after $MAX_REC recoveries at $NEXT / $TOTAL"; exit 4; }
    recover "$RECOVERIES" || recover 2 || { log "recovery failed at $NEXT / $TOTAL"; exit 2; }
    FAILS=0
  else
    sleep 3
  fi
done
log "done: $TOTAL frames in $OUT"
