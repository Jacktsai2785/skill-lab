#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STUB="$ROOT/tests/claude-stub.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/lib-review-test.XXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
chmod +x "$STUB"

fail() { echo "FAIL: $*" >&2; exit 1; }
expect_eq() { [ "$1" = "$2" ] || fail "expected '$2', got '$1'"; }
call_count() { wc -l < "$REVIEW_CALL_LOG" | tr -d ' '; }

export REVIEW_CACHE_DIR="$TMP/cache"
export REVIEW_CALL_LOG="$TMP/calls.log"
export REVIEW_ARGS_LOG="$TMP/args.log"
export CLAUDE_BIN="$STUB"
export REVIEW_TIMEOUT=1
: > "$REVIEW_CALL_LOG"
: > "$REVIEW_ARGS_LOG"

source "$ROOT/lib-review.sh"

expect_eq "$(review_timeout_for_hook pre-commit)" 300
expect_eq "$(review_timeout_for_hook pre-push)" 900
export REVIEW_TIMEOUT=1200
expect_eq "$(review_timeout_for_hook pre-push)" 1200
export REVIEW_TIMEOUT=1

repo="$TMP/repo"
git init -q "$repo"
git -C "$repo" config user.name test
git -C "$repo" config user.email test@example.invalid
printf 'base\n' > "$repo/file.txt"
git -C "$repo" add file.txt
SKIP_REVIEW=1 git -C "$repo" commit -qm base
printf 'staged change\n' >> "$repo/file.txt"
git -C "$repo" add file.txt

pushd "$repo" >/dev/null
base_tree="$(git rev-parse HEAD^{tree})"
target_tree="$(git write-tree)"
review_gate pre-commit "$base_tree" "$target_tree" "test staged change"
expect_eq "$(call_count)" 1
first_cwd="$(head -n 1 "$REVIEW_CALL_LOG")"
[ "$first_cwd" != "$repo" ] || fail "reviewer ran in the live repository"
case "$first_cwd" in */repo) ;; *) fail "reviewer did not run in isolated repo: $first_cwd" ;; esac
tr '\0' '\n' < "$REVIEW_ARGS_LOG" | grep -Fq 'Bash(git diff refs/review/base refs/review/target)' \
  || fail "exact isolated diff command was not granted"

# Same context reuses the explicit PASS without invoking the CLI again.
review_gate pre-commit "$base_tree" "$target_tree" "test staged change"
expect_eq "$(call_count)" 1

# Any untracked working-tree input changes the conservative cache key.
printf 'not staged\n' > untracked.txt
review_gate pre-commit "$base_tree" "$target_tree" "test staged change"
expect_eq "$(call_count)" 2

# The installed pre-commit entry point derives its own immutable trees and
# passes them to review_gate; this guards the public hook-to-library contract.
printf 'another staged change\n' >> file.txt
git add file.txt
"$ROOT/pre-commit"
expect_eq "$(call_count)" 3

# pre-push receives ref tuples via stdin and must derive base/target trees for
# that exact range, not the current working tree.
SKIP_REVIEW=1 git commit -qm second
push_base="$(git rev-parse HEAD~1)"
push_target="$(git rev-parse HEAD)"
printf 'refs/heads/main %s refs/heads/main %s\n' "$push_target" "$push_base" | "$ROOT/pre-push"
expect_eq "$(call_count)" 4

# Only an explicit final FAIL blocks. A CLI error remains fail-open and is
# never written as a cacheable PASS.
printf 'force a new context\n' > fail-context.txt
REVIEW_STUB_VERDICT=FAIL review_gate pre-commit "$base_tree" "$target_tree" "test explicit fail" \
  && fail "explicit VERDICT: FAIL did not block"
expect_eq "$(call_count)" 5
printf 'force another new context\n' > error-context.txt
REVIEW_STUB_RC=9 review_gate pre-commit "$base_tree" "$target_tree" "test cli error"
expect_eq "$(call_count)" 6
popd >/dev/null

# Initial commits have no HEAD; the hook still has a valid empty-tree base.
initial="$TMP/initial"
git init -q "$initial"
git -C "$initial" config user.name test
git -C "$initial" config user.email test@example.invalid
printf 'first\n' > "$initial/first.txt"
git -C "$initial" add first.txt
pushd "$initial" >/dev/null
empty_tree="$(git hash-object -t tree --stdin </dev/null)"
first_tree="$(git write-tree)"
review_gate pre-commit "$empty_tree" "$first_tree" "test initial commit"
popd >/dev/null
expect_eq "$(call_count)" 7

echo "PASS: lib-review isolation, timeout floor, cache key, and initial commit"
