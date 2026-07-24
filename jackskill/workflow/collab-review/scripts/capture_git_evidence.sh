#!/usr/bin/env bash
# Capture a small, immutable Git snapshot for collab-review. It never mutates
# the repository; it only creates the caller-selected, previously absent output directory.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 OUTPUT_DIR [BASE_REF]" >&2
  exit 2
fi

out_dir="$1"
base_ref="${2:-}"

if [[ -e "$out_dir" ]]; then
  echo "refusing to overwrite existing output path: $out_dir" >&2
  exit 2
fi
git rev-parse --show-toplevel >/dev/null 2>&1 || {
  echo "run this script inside a Git worktree" >&2
  exit 2
}
if [[ -n "$base_ref" ]]; then
  git rev-parse --verify "$base_ref" >/dev/null 2>&1 || {
    echo "unknown base ref: $base_ref" >&2
    exit 2
  }
fi

mkdir -p "$out_dir"
git status --short > "$out_dir/git-status.txt"
git diff --no-ext-diff > "$out_dir/working-tree.diff"
git diff --cached --no-ext-diff > "$out_dir/index.diff"
git log -20 --oneline > "$out_dir/recent-commits.txt"

if [[ -n "$base_ref" ]]; then
  git diff --no-ext-diff "$base_ref"...HEAD > "$out_dir/commit-range.diff"
fi

printf 'captured Git evidence in %s\n' "$out_dir"
