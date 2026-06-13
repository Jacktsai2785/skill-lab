# skill-lab — 個人 Skill 庫（專案規則）

這是 Jack 自己原創的 Claude Code skill 開發庫，與朋友的 `rivendell` repo **完全獨立**。

## 這個 repo 是什麼
- 放我自己原創的 skill（不是對 rivendell 的修改 / 適配）。
- 有自己的 GitHub remote，是跨裝置同步與備份的來源。

## 結構
- `skills/<category>/<name>/SKILL.md` —— 一個 skill 一個資料夾。
- `skills/<category>/<name>/references/` —— 該 skill 的補充參考文件。
- `deploy.sh` —— 把每個 skill symlink 進 `~/.claude/skills/`，全域可用。

## 規則
- **env-agnostic**：skill 內容不要寫死 mac/launchd 或 WSL/systemd；要嘛跨平台、要嘛靠執行期偵測。這個 repo 要能在任何裝置 clone 後直接用。
- **不依賴 rivendell**：不要 import rivendell 的 `sk` 工具鏈或 gstack skill；可選依賴（如 office-hours）一律寫成 optional，缺了也要能跑。
- 改完任何 skill → 跑 `./deploy.sh` 確認 symlink 正常。
- 新增 / 改名 skill → 更新 `README.md` 的 Skills 清單。
- commit 訊息結尾加：`Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
