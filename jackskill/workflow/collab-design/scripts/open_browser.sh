#!/usr/bin/env bash
# Best-effort cross-platform "open this local file or URL in the default browser".
# Falls back to printing the path when no opener is available (e.g. a
# headless/remote session with no local display) — that's not an error,
# just tell the caller where the file is so they can open it themselves.
set -uo pipefail
TARGET="$1"

if { [ -n "${WSL_DISTRO_NAME:-}" ] || grep -qi microsoft /proc/version 2>/dev/null; } \
   && command -v wslpath >/dev/null 2>&1; then
  # Some WSL installations omit Windows system directories from PATH even
  # though explorer.exe is available at its normal mounted location.
  EXPLORER="$(command -v explorer.exe 2>/dev/null || true)"
  if [ -z "$EXPLORER" ] && [ -x /mnt/c/Windows/explorer.exe ]; then
    EXPLORER=/mnt/c/Windows/explorer.exe
  fi
  if [ -z "$EXPLORER" ]; then
    echo "no Windows browser opener available on this WSL host — open manually: $TARGET" >&2
    exit 1
  fi
  # explorer.exe reports a nonzero exit code even on success — that's a
  # known WSL quirk, not a failure signal.
  if [[ "$TARGET" == http://* || "$TARGET" == https://* ]]; then
    "$EXPLORER" "$TARGET" >/dev/null 2>&1
  else
    "$EXPLORER" "$(wslpath -w "$TARGET")" >/dev/null 2>&1
  fi
  exit 0
fi
if [ "$(uname -s)" = "Darwin" ] && command -v open >/dev/null 2>&1; then
  open "$TARGET"
  exit 0
fi
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$TARGET" >/dev/null 2>&1 &
  exit 0
fi
echo "no browser opener available on this host — open manually: $TARGET" >&2
exit 1
