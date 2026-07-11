#!/usr/bin/env bash
# install.sh — 把 code-review git hooks 安裝為「全裝置生效」。
# 原理:symlink 到 ~/.githooks,並設 git config --global core.hooksPath ~/.githooks。
# 在另一台裝置:clone/pull skill-lab 後執行 ./hooks/install.sh 一次即可。
#
# 注意:設定 local core.hooksPath 的 repo(例如 husky 專案)不受影響(local 覆蓋 global);
# 依賴 .git/hooks 預設路徑的 repo,由 hook 內的 run_repo_hook 委派補跑。
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$HOME/.githooks"

for f in lib-review.sh pre-commit pre-push; do
  ln -sfn "$SRC/$f" "$HOME/.githooks/$f"
done
chmod +x "$SRC/pre-commit" "$SRC/pre-push"

git config --global core.hooksPath "$HOME/.githooks"

echo "✓ 已安裝:所有 repo 的 commit / push 都會先跑 /code-review xhigh"
echo "  跳過單次:SKIP_REVIEW=1 <git 指令> 或 --no-verify"
echo "  完全移除:git config --global --unset core.hooksPath"
