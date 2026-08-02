#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "--version" ]; then
  echo "claude-stub 1.0"
  exit 0
fi

printf '%s\n' "$PWD" >> "${REVIEW_CALL_LOG:?}"
printf '%s\0' "$@" >> "${REVIEW_ARGS_LOG:?}"
printf 'VERDICT: %s\n' "${REVIEW_STUB_VERDICT:-PASS}"
exit "${REVIEW_STUB_RC:-0}"
