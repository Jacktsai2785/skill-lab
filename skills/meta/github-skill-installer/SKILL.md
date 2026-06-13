---
name: github-skill-installer
description: >
  TRIGGER when: 使用者貼 GitHub URL（`*/skills/*` 路徑）+ 「下載並安裝」「安裝這個 skill」「全域使用」「import 這個 skill」。
  自動從第三方 GitHub 倉庫拉取單一 skill，安裝到本地 rivendell 或全域 ~/.claude/skills/。
  自動處理 frontmatter normalize、依賴腳本下載、permissions/hooks 註冊。
version: 1.0.0
tags: [installer, automation, github, meta, skill-distribution]
languages: all
when_to_use: |
  - 使用者貼 GitHub skill URL 並要求安裝
  - 跨 repo 共享 skill 到本地環境
  - 自動化 skill 集成流程（frontmatter + config + scripts）
---

## Overview

github-skill-installer 是一份自動化工具，可從第三方 GitHub 倉庫的 `skills/<name>/` 子目錄完整拉取並安裝單一 skill 到本機。

此 skill 解決的問題：
- **多檔協同安裝**：SKILL.md、config.json、observer-loop.sh、start-observer.sh、settings.json 等多個相依檔案需同步安裝
- **Frontmatter 標準化**：不同來源的 SKILL.md frontmatter 格式可能不一致，需自動驗證與修復
- **安裝位置選擇**：根據使用者需求決定安裝到本地 `./skills/<category>/<name>/` 或全域 `~/.claude/skills/<name>/`
- **Settings 整合**：自動在 settings.json 或 settings.local.json 中註冊 permissions 與 hooks

## 何時使用

**觸發場景 1：使用者貼 GitHub skill URL**

使用者：「下載這個 skill：https://github.com/affaan-m/everything-claude-code/blob/main/skills/continuous-learning-v2」

此時應呼叫本 skill，自動：
1. 辨識 URL 中的 `skills/continuous-learning-v2` 路徑
2. 拉取該目錄下的所有檔案
3. 檢驗 SKILL.md frontmatter
4. 提示使用者選擇安裝位置（本地或全域）
5. 完成安裝

**觸發場景 2：跨倉庫 Skill 共享**

使用者在多個 rivendell 實例或團隊間共享自開發的 skill，透過 GitHub 作為 SSOT（Single Source of Truth），其他人可直接用本 skill 匯入最新版本。

**觸發場景 3：Skill 的「自動更新」檢查**

監視某個外部 GitHub skill，定期檢查版本，有更新時提示或自動升級（需搭配 CronCreate 或 loop）。

## 執行步驟

### 步驟 1：解析 GitHub URL

接收使用者的 GitHub URL，抽取關鍵資訊：
- **完整倉庫 URL**：e.g., `https://github.com/affaan-m/everything-claude-code`
- **Skill 名稱**：URL 中 `skills/` 後的目錄名，e.g., `continuous-learning-v2`
- **分支**：預設 `main`（若 URL 含 `?ref=branch` 則使用指定分支）

使用正規表達式驗證 URL 格式：
```
https://github.com/[owner]/[repo]/blob/[branch]/skills/[skill-name]
或簡化：
https://github.com/[owner]/[repo]/skills/[skill-name]
```

若 URL 未含 `skills/`，則拒絕並提示「此 URL 不是 skill 路徑」。

### 步驟 2：檢索遠端 Skill 檔案

使用 GitHub API 或 raw.githubusercontent.com 拉取下列檔案（若存在）：

| 檔案 | 必需 | 用途 |
|------|------|------|
| `SKILL.md` | ✓ | Skill 定義與說明 |
| `config.json` | ✗ | Skill 配置（如 API key、模型參數） |
| `observer-loop.sh` / `start-observer.sh` | ✗ | 後臺執行腳本 |
| `settings.json` | ✗ | Claude Code 設定（permissions、hooks） |
| 其他相依檔案 | ✗ | 業務邏輯檔案、輔助腳本 |

**實作方式**：

使用 GitHub API（需 token）或 raw.githubusercontent.com 取得檔案內容。建議使用 `gh` CLI：

```bash
# 列舉目錄內容
gh api repos/{owner}/{repo}/contents/skills/{skill-name}

# 下載單檔
gh api repos/{owner}/{repo}/contents/skills/{skill-name}/SKILL.md
```

若無 GitHub token，亦可使用 curl + raw.githubusercontent.com：

```bash
curl -s https://raw.githubusercontent.com/{owner}/{repo}/{branch}/skills/{skill-name}/SKILL.md
```

### 步驟 3：驗證與標準化 Frontmatter

拉取 `SKILL.md` 後，檢驗其 frontmatter：

**必填欄位**：
- `name`：skill 識別名（應與 GitHub 目錄名一致）
- `description`：單行說明（<200 字）
- `version`（推薦）：版本號，e.g., `1.0.0`

**推薦欄位**：
- `tags`：分類標籤陣列，e.g., `[installer, automation, github]`
- `languages`：支援語言陣列，e.g., `[zh-TW, en]`，或 `all`

**標準化規則**：
1. 若 `name` 欄位缺失或與目錄名不符，自動設為目錄名
2. 若 `description` 過長（>200 字），截斷並提示使用者
3. 若 `version` 缺失，設為 `1.0.0`
4. 若 `tags` 缺失，設為 `[external]`
5. 若 `languages` 缺失，設為 `all`

修正後的 SKILL.md 應寫回至安裝位置。

### 步驟 4：檢查與整合 config.json

若遠端存在 `config.json`，檢查其結構：

**預期欄位**：
- `requiredEnvVars`：必需的環境變數陣列
- `optionalEnvVars`：可選的環境變數陣列
- `permissions`：此 skill 所需的 Claude Code 權限（e.g., `["run-bash", "edit-code"]`）
- `hooks`：此 skill 要註冊的 hooks（e.g., `[{"when": "on-file-change", "run": "validate.sh"}]`）

此檔案應複製到安裝位置，並於後續步驟中用於 settings 整合。

### 步驟 5：下載依賴腳本

檢查 config.json 中是否指定了依賴腳本（如 `observer-loop.sh`、`start-observer.sh` 等），逐個下載：

```bash
for script in observer-loop.sh start-observer.sh validate.sh; do
  if [ -f "config.json" ] && grep -q "$script" config.json; then
    curl -s https://raw.githubusercontent.com/{owner}/{repo}/{branch}/skills/{skill-name}/$script \
      -o {install-dir}/$script
    chmod +x {install-dir}/$script
  fi
done
```

所有腳本應設為可執行（`chmod +x`）。

### 步驟 6：選擇安裝位置

提示使用者選擇安裝位置：

**選項 A：本地安裝**（推薦，僅供此 rivendell 專案使用）
```
安裝位置：./skills/{category}/{skill-name}/
```

此時應提示使用者選擇分類（如 `meta`, `workflow`, `backend` 等），預設為 `external`。

**選項 B：全域安裝**（供所有 Claude Code 專案使用）
```
安裝位置：~/.claude/skills/{skill-name}/
```

此選項適用於跨多個專案共用的 skill。

根據使用者選擇，確定最終安裝路徑 `{install-dir}`。

### 步驟 7：複製檔案並創建目錄結構

創建安裝目錄（若不存在）並複製所有檔案：

```bash
mkdir -p {install-dir}
cp SKILL.md {install-dir}/
cp config.json {install-dir}/ 2>/dev/null || true
cp *.sh {install-dir}/ 2>/dev/null || true
chmod +x {install-dir}/*.sh 2>/dev/null || true
```

同時記錄安裝來源（便於日後更新追蹤）：

```bash
cat > {install-dir}/.github-source << EOF
repo: {owner}/{repo}
branch: {branch}
skill-name: {skill-name}
imported-at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF
```

### 步驟 8：註冊 Permissions 與 Hooks

若 config.json 中包含 `permissions` 與 `hooks` 欄位，應自動在 settings.json 或 settings.local.json 中註冊：

**針對本地安裝**：更新 `.claude/settings.json`

```json
{
  "permissions": {
    "allow": {
      "run-bash": ["*.sh"],
      "edit-code": ["{install-dir}/**"]
    }
  },
  "hooks": [
    {
      "when": "on-file-change",
      "watch": "{install-dir}/source.ts",
      "run": "bash {install-dir}/validate.sh"
    }
  ]
}
```

**針對全域安裝**：更新 `~/.claude/settings.json`

同時提示使用者是否需要手動驗證這些權限設定。

### 步驟 9：驗證安裝成功

檢查下列項目確認安裝無誤：

```bash
# 驗證 SKILL.md 存在與有效
[ -f {install-dir}/SKILL.md ] && echo "✓ SKILL.md found"
grep -q "^name:" {install-dir}/SKILL.md && echo "✓ Frontmatter valid"

# 驗證腳本可執行
[ -x {install-dir}/observer-loop.sh ] && echo "✓ Scripts are executable"

# 驗證設定已整合
grep -q "{skill-name}" ~/.claude/settings.json && echo "✓ Settings registered"
```

若驗證失敗，應回滾安裝（刪除相關檔案並撤銷 settings 更改），並提示使用者錯誤原因。

## 注意事項

### 限制

1. **GitHub 速率限制**：GitHub API 無 token 時限制為 60 req/hour，建議提示使用者設定 `GITHUB_TOKEN` 環境變數以提高限制至 5000 req/hour。

2. **Skill 衝突**：若本地已存在同名 skill，應提示使用者選擇「覆蓋」「備份舊版」或「取消」，不應自動覆蓋。

3. **相依性檢查**：本 skill 無法檢查 skill 的執行時相依性（如特定 Python 版本、npm 套件等），安裝後應由使用者自行驗證。

4. **Settings 衝突**：若 config.json 中的 permissions/hooks 與既有設定衝突，應提示使用者手動審核而非自動合併。

5. **Frontmatter 編碼**：假定所有遠端 SKILL.md 均為 UTF-8 編碼；若遭遇編碼問題，應轉換為 UTF-8 後寫回。

### 已知陷阱

1. **URL 變異**：GitHub 支援多種 URL 格式（`tree/main` vs `blob/main`、末尾 `/` 等），應寬鬆解析而非嚴格驗證。

2. **分支不存在**：若指定的分支不存在，應改用 `main`（若存在），或提示使用者指定正確分支。

3. **私有倉庫**：若倉庫為私有，需 GitHub token 驗證，無 token 時應提示使用者「無法存取私有倉庫」。

4. **部分檔案缺失**：若 config.json 存在但指定的腳本不存在，應記錄警告但不中止安裝；若 SKILL.md 本身缺失，應完全中止並報錯。

5. **設定回滾**：安裝後若使用者手動編輯 settings.json 並保存，之後若需重新安裝則應謹慎處理，避免覆蓋使用者自訂設定。