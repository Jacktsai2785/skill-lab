#!/usr/bin/env bash
# lib-review.sh — pre-commit / pre-push 共用的 code-review gate。
# 由 hook source，不直接執行。
#
# 安全模型：只讓 reviewer 看 immutable base_tree / target_tree 的隔離 repo；
# timeout / CLI error / 沒有明確 verdict 一律維持既有 fail-open。只有明確 FAIL
# 才阻擋。PASS cache 僅在「完整上下文完全相同」時重用。

REVIEW_CACHE_SCHEMA_VERSION="2"
REVIEW_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

review_warn() {
  echo "⚠  $*" >&2
}

review_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | awk '{print $1}'
  else
    # git is already a hard dependency of these hooks and gives us a stable
    # content digest when common sha256 tools are unavailable.
    git hash-object --stdin
  fi
}

review_file_digest() {
  local path="$1"
  if [ -f "$path" ]; then
    review_sha256 < "$path"
  else
    printf '%s' '<missing>' | review_sha256
  fi
}

review_timeout_for_hook() {
  local hook_name="$1" minimum requested
  case "$hook_name" in
    pre-commit) minimum=300 ;;
    pre-push) minimum=900 ;;
    *)
      review_warn "未知的 hook 名稱 $hook_name；使用 900 秒保守下限"
      minimum=900
      ;;
  esac
  requested="${REVIEW_TIMEOUT:-$minimum}"
  if ! [[ "$requested" =~ ^[0-9]+$ ]]; then
    review_warn "REVIEW_TIMEOUT=$requested 不是秒數；使用 ${minimum}s"
    printf '%s\n' "$minimum"
  elif [ "$requested" -lt "$minimum" ]; then
    review_warn "REVIEW_TIMEOUT=${requested}s 低於 ${hook_name} 的 ${minimum}s 下限；已提升"
    printf '%s\n' "$minimum"
  else
    printf '%s\n' "$requested"
  fi
}

review_select_effort() {
  local requested="${REVIEW_EFFORT:-xhigh}"
  case "$requested" in
    xhigh) printf '%s\n' xhigh ;;
    medium|high)
      if [ "${REVIEW_ALLOW_LOWER_EFFORT:-0}" = "1" ]; then
        printf '%s\n' "$requested"
      else
        review_warn "REVIEW_EFFORT=$requested 需要 REVIEW_ALLOW_LOWER_EFFORT=1；維持 xhigh"
        printf '%s\n' xhigh
      fi
      ;;
    *)
      review_warn "未知 REVIEW_EFFORT=$requested；維持 xhigh"
      printf '%s\n' xhigh
      ;;
  esac
}

review_repo_identity() {
  local root git_dir origin
  root="$(git rev-parse --show-toplevel 2>/dev/null)" || return 1
  git_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || return 1
  origin="$(git config --get remote.origin.url 2>/dev/null || true)"
  printf 'root=%s\ngit_dir=%s\norigin=%s\n' "$root" "$git_dir" "$origin" | review_sha256
}

review_fs_state_fingerprint() {
  # The reviewer is isolated from these files, but keeping their fingerprint
  # in the key prevents a cached PASS from outliving a changed working tree if
  # a future CLI/tool policy exposes more context than intended.
  local unstaged_digest records_digest path content_digest diff_file paths_file records_file
  diff_file="$(mktemp "${TMPDIR:-/tmp}/review-fs-diff.XXXXXX")" || return 1
  paths_file="$(mktemp "${TMPDIR:-/tmp}/review-fs-paths.XXXXXX")" || { rm -f -- "$diff_file"; return 1; }
  records_file="$(mktemp "${TMPDIR:-/tmp}/review-fs-records.XXXXXX")" || {
    rm -f -- "$diff_file" "$paths_file"; return 1;
  }
  if ! git diff --no-ext-diff --binary > "$diff_file" 2>/dev/null || \
      ! git ls-files --others --exclude-standard -z > "$paths_file"; then
    rm -f -- "$diff_file" "$paths_file" "$records_file"
    return 1
  fi
  while IFS= read -r -d '' path; do
    content_digest="$(git hash-object --no-filters -- "$path" 2>/dev/null)" || {
      rm -f -- "$diff_file" "$paths_file" "$records_file"
      return 1
    }
    printf '%s\0%s\n' "$path" "$content_digest" >> "$records_file" || {
      rm -f -- "$diff_file" "$paths_file" "$records_file"
      return 1
    }
  done < "$paths_file"
  unstaged_digest="$(review_sha256 < "$diff_file")"
  records_digest="$(review_sha256 < "$records_file")"
  rm -f -- "$diff_file" "$paths_file" "$records_file"
  printf 'unstaged=%s\nuntracked=%s\n' "$unstaged_digest" "$records_digest" | review_sha256
}

review_policy_digest() {
  local root="$1" path
  {
    printf 'schema=%s\n' "$REVIEW_CACHE_SCHEMA_VERSION"
    for path in \
      "$REVIEW_LIB_DIR/lib-review.sh" \
      "$REVIEW_LIB_DIR/review-policy.conf" \
      "$root/AGENTS.md" \
      "$root/CLAUDE.md" \
      "${HOME:-}/.claude/CLAUDE.md"; do
      printf '%s=%s\n' "$path" "$(review_file_digest "$path")"
    done
  } | review_sha256
}

review_cache_path() {
  local key="$1" root="${REVIEW_CACHE_DIR:-${HOME:-}/.githooks/review-cache}"
  printf '%s/%s/%s.entry\n' "$root" "${key:0:2}" "$key"
}

review_cache_lookup() {
  local key="$1" effort="$2" path expires now
  path="$(review_cache_path "$key")"
  [ -r "$path" ] || return 1
  expires="$(sed -n 's/^expires_at=//p' "$path" | head -n 1)"
  now="$(date +%s)"
  [[ "$expires" =~ ^[0-9]+$ ]] && [ "$expires" -gt "$now" ] || return 1
  grep -qx "schema=$REVIEW_CACHE_SCHEMA_VERSION" "$path" || return 1
  grep -qx "effort=$effort" "$path" || return 1
  grep -qx 'verdict=PASS' "$path" || return 1
  return 0
}

review_cache_store_pass() {
  local key="$1" effort="$2" path dir tmp now ttl expires
  path="$(review_cache_path "$key")"
  dir="$(dirname "$path")"
  now="$(date +%s)"
  ttl="${REVIEW_CACHE_TTL_SECONDS:-604800}"
  [[ "$ttl" =~ ^[0-9]+$ ]] || ttl=604800
  expires=$((now + ttl))
  (umask 077 && mkdir -p "$dir") || return 1
  tmp="$(mktemp "$dir/.${key}.XXXXXX")" || return 1
  {
    printf 'schema=%s\n' "$REVIEW_CACHE_SCHEMA_VERSION"
    printf 'effort=%s\n' "$effort"
    printf 'verdict=PASS\n'
    printf 'created_at=%s\n' "$now"
    printf 'expires_at=%s\n' "$expires"
  } > "$tmp" || { rm -f -- "$tmp"; return 1; }
  chmod 600 "$tmp" && mv -f -- "$tmp" "$path"
}

review_cleanup_context() {
  [ -n "${REVIEW_SOURCE_BASE_REF:-}" ] && git update-ref -d "$REVIEW_SOURCE_BASE_REF" >/dev/null 2>&1 || true
  [ -n "${REVIEW_SOURCE_TARGET_REF:-}" ] && git update-ref -d "$REVIEW_SOURCE_TARGET_REF" >/dev/null 2>&1 || true
  [ -n "${REVIEW_CONTEXT_DIR:-}" ] && rm -rf -- "$REVIEW_CONTEXT_DIR"
  REVIEW_CONTEXT_DIR=""
  REVIEW_SOURCE_BASE_REF=""
  REVIEW_SOURCE_TARGET_REF=""
}

review_prepare_context() {
  local base_tree="$1" target_tree="$2" nonce base_commit target_commit bundle repo
  REVIEW_CONTEXT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/collab-review.XXXXXX")" || return 1
  nonce="${$}.${RANDOM}"
  REVIEW_SOURCE_BASE_REF="refs/collab-review-tmp/${nonce}/base"
  REVIEW_SOURCE_TARGET_REF="refs/collab-review-tmp/${nonce}/target"
  base_commit="$(git -c user.name=collab-review -c user.email=collab-review@local \
    commit-tree "$base_tree" -m 'collab review base' 2>/dev/null)" || { review_cleanup_context; return 1; }
  target_commit="$(git -c user.name=collab-review -c user.email=collab-review@local \
    commit-tree "$target_tree" -m 'collab review target' 2>/dev/null)" || { review_cleanup_context; return 1; }
  git update-ref "$REVIEW_SOURCE_BASE_REF" "$base_commit" && \
    git update-ref "$REVIEW_SOURCE_TARGET_REF" "$target_commit" || { review_cleanup_context; return 1; }
  bundle="$REVIEW_CONTEXT_DIR/context.bundle"
  git bundle create "$bundle" "$REVIEW_SOURCE_BASE_REF" "$REVIEW_SOURCE_TARGET_REF" >/dev/null 2>&1 || { review_cleanup_context; return 1; }
  repo="$REVIEW_CONTEXT_DIR/repo"
  git init -q "$repo" && \
    git -C "$repo" fetch -q "$bundle" \
      "$REVIEW_SOURCE_BASE_REF:refs/review/base" \
      "$REVIEW_SOURCE_TARGET_REF:refs/review/target" && \
    git -C "$repo" checkout -q --detach refs/review/target || { review_cleanup_context; return 1; }
  # The source refs can disappear once the bundle has been fetched. The
  # isolated repository keeps only the two review refs and their reachable
  # objects, not unrelated branches/reflogs from the live repository.
  git update-ref -d "$REVIEW_SOURCE_BASE_REF" >/dev/null 2>&1 || true
  git update-ref -d "$REVIEW_SOURCE_TARGET_REF" >/dev/null 2>&1 || true
  REVIEW_SOURCE_BASE_REF=""
  REVIEW_SOURCE_TARGET_REF=""
  return 0
}

review_allowed_tools() {
  local root="$1"
  printf 'Read(%s/**),Glob(%s/**),Grep(%s/**),Bash(git diff refs/review/base refs/review/target),Bash(git log refs/review/base..refs/review/target),Bash(git show refs/review/base),Bash(git show refs/review/target),Bash(git show refs/review/base:*),Bash(git show refs/review/target:*),Bash(git status)' \
    "$root" "$root" "$root"
}

review_build_prompt() {
  local hook_name="$1" effort="$2" base_tree="$3" target_tree="$4" scope_prompt="$5"
  cat <<EOF
/code-review $effort — $scope_prompt
你正在隔離的審查 repo 中工作；只能使用 refs/review/base 與 refs/review/target。
本次 immutable context：hook=$hook_name, base_tree=$base_tree, target_tree=$target_tree。
規則：只列 CONFIRMED 或高信心的 correctness 問題；不要修改任何檔案。
審查結束後，最後一行必須單獨輸出以下其中之一：
VERDICT: PASS  (沒有 CONFIRMED 的 correctness 問題)
VERDICT: FAIL  (存在 CONFIRMED 的 correctness 問題)
EOF
}

review_gate() {
  local hook_name="$1" base_tree="$2" target_tree="$3" scope_prompt="$4"
  local bin effort timeout_seconds root repo_identity fs_fingerprint policy_digest
  local prompt prompt_digest cache_key allowed_tools out rc

  if [ "${SKIP_REVIEW:-0}" = "1" ]; then
    echo "⏭  SKIP_REVIEW=1 — 跳過 code review"
    return 0
  fi
  bin="${CLAUDE_BIN:-claude}"
  if ! command -v "$bin" >/dev/null 2>&1; then
    review_warn "找不到 claude CLI — 跳過 code review (fail-open)"
    return 0
  fi
  git cat-file -e "${base_tree}^{tree}" 2>/dev/null && \
    git cat-file -e "${target_tree}^{tree}" 2>/dev/null || {
      review_warn "無法建立 immutable review tree — 跳過 code review (fail-open)"
      return 0
    }
  root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    review_warn "不在 git repository 中 — 跳過 code review (fail-open)"
    return 0
  }
  effort="$(review_select_effort)"
  timeout_seconds="$(review_timeout_for_hook "$hook_name")"
  prompt="$(review_build_prompt "$hook_name" "$effort" "$base_tree" "$target_tree" "$scope_prompt")"
  prompt_digest="$(printf '%s' "$prompt" | review_sha256)"
  repo_identity="$(review_repo_identity)" || repo_identity="unavailable"
  policy_digest="$(review_policy_digest "$root")"
  fs_fingerprint="$(review_fs_state_fingerprint)" || {
    review_warn "無法計算 working-tree fingerprint；停用本次 PASS cache"
    fs_fingerprint=""
  }
  cache_key="$(printf 'schema=%s\nhook=%s\nrepo=%s\nbase=%s\ntarget=%s\nfs=%s\nprompt=%s\npolicy=%s\ncli=%s\neffort=%s\n' \
    "$REVIEW_CACHE_SCHEMA_VERSION" "$hook_name" "$repo_identity" "$base_tree" "$target_tree" \
    "$fs_fingerprint" "$prompt_digest" "$policy_digest" "$("$bin" --version 2>/dev/null | head -n 1)" "$effort" | review_sha256)"
  if [ -n "$fs_fingerprint" ] && review_cache_lookup "$cache_key" "$effort"; then
    echo "✅ code review PASS cache 命中 ($effort；完整上下文相同)"
    return 0
  fi

  echo "🔍 code review ($effort) 進行中… (逾時 ${timeout_seconds}s；跳過：SKIP_REVIEW=1 或 --no-verify)"
  if ! review_prepare_context "$base_tree" "$target_tree"; then
    review_warn "無法建立隔離審查環境 — 跳過 code review (fail-open；不寫 PASS cache)"
    return 0
  fi
  allowed_tools="$(review_allowed_tools "$REVIEW_CONTEXT_DIR/repo")"
  # Use an if-condition to capture a non-zero CLI status even when the hook
  # process itself was started with `set -e`; the policy below must get the
  # chance to apply its deliberate fail-open behavior.
  if out="$(cd "$REVIEW_CONTEXT_DIR/repo" && \
    env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX \
      timeout "$timeout_seconds" "$bin" -p "$prompt" --allowedTools "$allowed_tools" 2>&1)"; then
    rc=0
  else
    rc=$?
  fi
  review_cleanup_context

  echo "$out"
  echo "────────────────────────────────"
  if [ "$rc" -eq 124 ]; then
    review_warn "code review 逾時 — 放行 (fail-open；不寫 PASS cache)"
    return 0
  fi
  if [ "$rc" -ne 0 ]; then
    review_warn "claude 執行失敗 (rc=$rc) — 放行 (fail-open；不寫 PASS cache)"
    return 0
  fi
  if printf '%s\n' "$out" | tail -n 1 | grep -qx 'VERDICT: FAIL'; then
    return 1
  fi
  if printf '%s\n' "$out" | tail -n 1 | grep -qx 'VERDICT: PASS'; then
    if [ -n "$fs_fingerprint" ]; then
      review_cache_store_pass "$cache_key" "$effort" || review_warn "無法寫入 PASS cache；下次會重新審查"
    fi
    return 0
  fi
  review_warn "未取得最後一行明確 VERDICT — 放行 (fail-open；不寫 PASS cache)"
  return 0
}

# 委派：全域 hooksPath 會遮蔽 repo 自己的 .git/hooks/<name>，這裡補跑它。
# 注意：必須用 --git-dir 拼出實體路徑；--git-path hooks 會回傳 hooksPath 設定值
# (= ~/.githooks 自己)，曾造成無限遞迴。
run_repo_hook() {
  local name="$1"; shift
  local repo_hook self
  repo_hook="$(git rev-parse --git-dir 2>/dev/null)/hooks/$name"
  self="$(readlink -f "${BASH_SOURCE[1]:-/dev/null}")"
  if [ -x "$repo_hook" ] && [ "$(readlink -f "$repo_hook")" != "$self" ]; then
    "$repo_hook" "$@"
    return $?
  fi
  return 0
}
