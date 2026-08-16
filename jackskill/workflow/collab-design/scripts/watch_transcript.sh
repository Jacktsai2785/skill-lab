#!/usr/bin/env bash
# Generate the collab live-transcript HTML, open it in the default browser,
# then keep regenerating it every ~15s (the page itself meta-refreshes every
# 12s) so a tab left open keeps showing new proposal/review/synthesis
# content while the run progresses in the background — without anyone
# polling `collab status` by hand. It exits only at a terminal state. A
# resumable pause stays under observation, so a later user-initiated resume
# updates this same page instead of leaving a stale paused transcript. The
# watcher never answers a card or resumes a run by itself.
set -uo pipefail
RUN_ID="$1"
OUT="$2"
TOPIC="${3:-}"   # optional: short human label, e.g. "skill-lab 全域 git hook 開放式設計"
                 # — falls back to a truncated brief.prompt when omitted
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLAB_BIN="${COLLAB_BIN:-collab}"
DASHBOARD_PORT="${COLLAB_DASHBOARD_PORT:-8787}"
DASHBOARD_ORIGIN="http://127.0.0.1:${DASHBOARD_PORT}"
# A collab design opens its own focused page. The dashboard root remains an
# intentional historical overview, reachable from the focused page's link.
DASHBOARD_URL="${DASHBOARD_ORIGIN}/?run=${RUN_ID}"
DASHBOARD_LOG="${TMPDIR:-/tmp}/collab-dashboard-${DASHBOARD_PORT}.log"

render() {
  COLLAB_DASHBOARD_URL="$DASHBOARD_URL" \
    python3 "$SCRIPT_DIR/collab_transcript.py" "$RUN_ID" "$OUT" "$TOPIC" >/dev/null
}

dashboard_ready() {
  curl --silent --show-error --fail --max-time 1 \
    "$DASHBOARD_ORIGIN/api/runs" >/dev/null 2>&1
}

ensure_dashboard() {
  if dashboard_ready; then
    return 0
  fi
  # Detach the server from this shell. The watcher remains alive during a
  # pending decision and will re-create a crashed dashboard on its next poll.
  nohup "$COLLAB_BIN" ui --port "$DASHBOARD_PORT" \
    </dev/null >"$DASHBOARD_LOG" 2>&1 &
  for _ in $(seq 1 12); do
    sleep 0.25
    if dashboard_ready; then
      return 0
    fi
  done
  echo "dashboard did not become ready; inspect $DASHBOARD_LOG" >&2
  return 1
}

render
"$SCRIPT_DIR/open_browser.sh" "$OUT" || true

for i in $(seq 1 120); do
  STATUS_LINE=$("$COLLAB_BIN" status "$RUN_ID" 2>&1 | head -1)
  echo "[$i] $STATUS_LINE"
  if echo "$STATUS_LINE" | grep -q "awaiting_user_decision"; then
    render
    if ensure_dashboard; then
      if [ "${DECISION_ALERTED:-0}" -eq 0 ]; then
        "$SCRIPT_DIR/open_browser.sh" "$DASHBOARD_URL" || true
        echo "decision required; opened $DASHBOARD_URL for $RUN_ID"
        DECISION_ALERTED=1
      fi
    fi
    # Keep the watcher (and its local dashboard child) alive while the human
    # decides. This is still read-only: only a button click in the dashboard
    # can call answer(). The next loop notices the state change.
    sleep 15
    render
    continue
  fi
  if echo "$STATUS_LINE" | grep -qE "completed|cancelled|escalated|failed"; then
    echo "reached a stopping state, generating the durable report and final handoff"
    # The live transcript links to this sibling file. Generate it before the
    # final render so the primary completion action never points at a missing
    # report. Dashboard/browser notifications remain a best-effort extra.
    "$COLLAB_BIN" report "$RUN_ID" --format html >/dev/null 2>&1 || \
      echo "warning: final report generation failed for $RUN_ID" >&2
    render
    # A completed run should be as visible as a pending decision.  The
    # dashboard uses a browser notification (when the user has granted it)
    # and always renders the deterministic "what changed" summary.
    if ensure_dashboard; then
      "$SCRIPT_DIR/open_browser.sh" "$DASHBOARD_URL" || true
      echo "run finished or paused; opened $DASHBOARD_URL for $RUN_ID"
    fi
    exit 0
  fi
  if echo "$STATUS_LINE" | grep -q "paused_"; then
    # A pause may need local investigation before the user resumes. Keep
    # rendering so this same file advances when that user-authorized resume
    # happens; the watcher itself remains read-only.
    render
    if ensure_dashboard; then
      if [ "${PAUSE_ALERTED:-0}" -eq 0 ]; then
        "$SCRIPT_DIR/open_browser.sh" "$DASHBOARD_URL" || true
        echo "run paused; opened $DASHBOARD_URL and continuing to watch for a user-initiated resume"
        PAUSE_ALERTED=1
      fi
    fi
    sleep 15
    render
    continue
  fi
  sleep 15
  render
done
echo "watch loop hit its iteration cap (~30 min); exiting so it doesn't run forever." \
     "Re-launch this script with the same RUN_ID/OUT after a resume to keep watching."
