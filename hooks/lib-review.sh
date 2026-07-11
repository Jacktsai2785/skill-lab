#!/usr/bin/env bash
# lib-review.sh — commit/push code-review gate 的共用邏輯。
# 由 pre-commit / pre-push 兩個 hook source,不直接執行。
#
# 環境變數:
#   SKIP_REVIEW=1        跳過本次審查(另一逃生口:git 原生 --no-verify)
#   REVIEW_TIMEOUT=900   單次審查逾時秒數(預設 15 分鐘)
#   REVIEW_EFFORT=xhigh  審查力度,傳給 /code-review
#   CLAUDE_BIN=claude    claude CLI 路徑(測試時可換成 stub)
#
# 失敗策略:claude 不存在 / 執行失敗 / 逾時 → fail-open(警告後放行),
# 只有審查明確輸出 VERDICT: FAIL 才擋下。

review_gate() {
  local scope_prompt="$1"

  if [ "${SKIP_REVIEW:-0}" = "1" ]; then
    echo "⏭  SKIP_REVIEW=1 — 跳過 code review"
    return 0
  fi

  local bin="${CLAUDE_BIN:-claude}"
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "⚠  找不到 claude CLI — 跳過 code review(fail-open)"
    return 0
  fi

  local effort="${REVIEW_EFFORT:-xhigh}"
  echo "🔍 code review ($effort) 進行中… (逾時 ${REVIEW_TIMEOUT:-900}s;跳過:SKIP_REVIEW=1 或 --no-verify)"

  local out rc
  # 注意:--allowedTools 是可變參數,prompt 必須放在它之前,否則會被當成工具名吞掉
  out=$(timeout "${REVIEW_TIMEOUT:-900}" "$bin" -p \
    "/code-review $effort — ${scope_prompt}
規則:只列 CONFIRMED 或高信心的 correctness 問題;不要修改任何檔案。
審查結束後,最後一行必須單獨輸出以下其中之一:
VERDICT: PASS  (沒有 CONFIRMED 的 correctness 問題)
VERDICT: FAIL  (存在 CONFIRMED 的 correctness 問題)" \
    --allowedTools "Read,Grep,Glob,Bash(git diff:*),Bash(git log:*),Bash(git show:*),Bash(git status:*)" 2>&1)
  rc=$?

  echo "$out"
  echo "────────────────────────────────"

  if [ $rc -eq 124 ]; then
    echo "⚠  code review 逾時 — 放行(fail-open)"
    return 0
  fi
  if [ $rc -ne 0 ]; then
    echo "⚠  claude 執行失敗 (rc=$rc) — 放行(fail-open)"
    return 0
  fi
  if printf '%s\n' "$out" | grep -q "VERDICT: FAIL"; then
    return 1
  fi
  if ! printf '%s\n' "$out" | grep -q "VERDICT: PASS"; then
    echo "⚠  未取得明確 VERDICT — 放行(fail-open)"
  fi
  return 0
}

# 委派:全域 hooksPath 會遮蔽 repo 自己的 .git/hooks/<name>,這裡補跑它。
# 注意:必須用 --git-dir 拼出實體路徑;--git-path hooks 會回傳 hooksPath 設定值
# (= ~/.githooks 自己),曾造成無限遞迴。
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
