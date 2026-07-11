#!/usr/bin/env bash
# 把 skill-lab/jackskill/<cat>/<name>/ 全部 symlink 進 ~/.claude/skills/，讓所有專案全域可用。
# 安全護欄：若目標已是「真實目錄」（非 symlink），跳過並警告——避免遮蔽陷阱。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$HOME/.claude/skills"
mkdir -p "$TARGET"

count=0
for skill_md in "$REPO_DIR"/jackskill/*/*/SKILL.md; do
  [ -e "$skill_md" ] || continue
  skill_dir="$(dirname "$skill_md")"
  name="$(basename "$skill_dir")"
  link="$TARGET/$name"

  if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "⚠️  跳過 $name：$link 已是真實目錄（會遮蔽 symlink，請先手動處理）"
    continue
  fi
  ln -sfn "$skill_dir" "$link"
  echo "✓ $name → $link"
  count=$((count + 1))
done

echo "已部署 $count 個 skill。"
