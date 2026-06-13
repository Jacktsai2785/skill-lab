---
name: cross-project-docs-symlink-bridge
description: |
  TRIGGER when: 需要在主知識庫彙聚多個 Claude Code 子專案的文件，建立跨專案文件橋接。
  when_to_use: 設置多專案知識庫協作、主知識庫要聚合各子專案 docs/、需要統一文件查詢與導航。
version: 1.0.0
tags:
  - knowledge-management
  - multi-project
  - symlink
  - documentation
languages: all
---

## Overview

在主知識庫（如 `jk_nb`）建立 `wiki/_external/<short-name>/` 結構，用 symlink 連接各子專案的 `docs/` 資料夾。這樣可以：
- 將多個子專案的文件聚合到一個中央知識庫
- 保持原始檔案在各自專案內，無重複維護
- 在主知識庫建立統一的「權威文件」索引
- 配置 dead-link lint 和 agent 只讀護欄，確保完整性和安全性

## 何時使用

- **多專案文件彙聚**：jk_nb 整合 mops_dbs、taiwan-company、其他 Claude Code 子專案的文件
- **跨專案導航**：用戶在主知識庫查詢時，能無縫存取所有子專案的 docs
- **新增子專案**：為新的子專案註冊 symlink，自動納入文件聚合

## 執行步驟

### 步驟 1：準備主知識庫結構

在主知識庫根目錄確認或建立以下結構：

```
wiki/
  _external/
    KNOWLEDGE_REGISTRY.md
    mops-dbs/                    # symlink → ~/mops_dbs/docs
    taiwan-company/              # symlink → ~/taiwan-company/docs
    [other-projects]/
  _local/
    [主知識庫本地文件]
```

### 步驟 2：建立 KNOWLEDGE_REGISTRY.md

在 `wiki/_external/` 目錄建立中央索引：

```
# Cross-Project Knowledge Registry

本檔案記錄主知識庫與各子專案的 symlink 對應關係及文件來源。

## Registered Projects

| Short Name | Source Path | Symlink Target | Last Updated |
|---|---|---|---|
| mops-dbs | ~/mops_dbs/docs | `wiki/_external/mops-dbs/` | 2026-06-13 |
| taiwan-company | ~/taiwan-company/docs | `wiki/_external/taiwan-company/` | 2026-06-13 |

## Navigation

- 閱讀各子專案文件：跳轉至 `wiki/_external/<short-name>/README.md` 或對應主題檔
- 搜尋跨專案內容：用主知識庫的全文搜尋工具（grep, Obsidian, etc.）
- 新增子專案：見 「Adding a New Project」章節

## Adding a New Project

1. 確認子專案有 `docs/` 資料夾
2. 在 `wiki/_external/` 執行：
   ```bash
   ln -s /path/to/project/docs <short-name>
   ```
3. 在此檔案 Registered Projects 表格新增一列
4. 執行 dead-link lint 驗證（見下一步）

## Dead-Link Lint Rules

執行檢查命令（在主知識庫根目錄）：

```bash
find wiki/_external -type l -exec test ! -e {} \; -print
```

此命令列出所有失效的 symlink。若有失效連結，檢查：
- 子專案資料夾是否移動或刪除
- symlink 路徑是否正確（使用絕對路徑避免相對路徑脆弱性）

## Agent Guardrails (Read-Only)

為防止 AI agent 意外修改或建立文件，配置以下護欄：

- **禁止寫入** `wiki/_external/` 下的任何檔案（除了自動生成的索引）
- **禁止建立新 symlink**：symlink 建立應由人工審核
- **禁止刪除 symlink**：即使檔案參考消失，保留 symlink 待人工判斷

在專案 `.claude/settings.json` 中配置：

```json
{
  "restrictions": {
    "blockedPaths": [
      "wiki/_external/**"
    ],
    "allowedOperations": [
      {
        "path": "wiki/_external/**",
        "operations": ["read"]
      }
    ]
  }
}
```

### 步驟 3：建立 Symlink

假設主知識庫為 `~/jk_nb`，子專案如 `~/mops_dbs`：

```bash
cd ~/jk_nb/wiki/_external

# 為 mops_dbs 建立 symlink
ln -s ~/mops_dbs/docs mops-dbs

# 為 taiwan-company 建立 symlink
ln -s ~/taiwan-company/docs taiwan-company

# 驗證
ls -l
```

若需要相對路徑（跨機器遷移時更穩健），使用 `realpath` 計算深度：

```bash
# 計算相對路徑（以 jk_nb 為基準）
# jk_nb/wiki/_external/mops-dbs → ~/mops_dbs/docs
# 相對路徑：../../mops_dbs/docs

ln -s ../../../mops_dbs/docs mops-dbs
```

### 步驟 4：驗證與除錯

```bash
# 檢查所有 symlink 有效性
find wiki/_external -type l | while read link; do
  if [ -L "$link" ] && [ ! -e "$link" ]; then
    echo "❌ Dead link: $link"
  else
    echo "✓ Valid: $link"
  fi
done

# 列出所有 symlink 目標
find wiki/_external -type l -exec sh -c 'echo "{}  →  $(readlink -f {})"' \;
```

### 步驟 5：更新 KNOWLEDGE_REGISTRY.md

每次新增或修改 symlink 後，更新表格記錄當日期，例如：

```
| mops-dbs | ~/mops_dbs/docs | `wiki/_external/mops-dbs/` | 2026-06-13 |
```

## 注意事項

### 已知限制

1. **相對路徑脆弱性**：若主知識庫或子專案移動位置，相對路徑 symlink 會失效。使用絕對路徑或在 KNOWLEDGE_REGISTRY.md 記錄完整來源路徑。

2. **跨作業系統相容性**：macOS 和 Linux 的 symlink 相容，但 Windows (WSL2) 可能需要額外設定（啟用開發者模式或 WSL interop）。

3. **Git 追蹤**：Git 會追蹤 symlink 本身，不追蹤目標檔案。確認 `.gitignore` 不會誤刪 symlink，但也可考慮在主知識庫 .gitignore 中忽略 `wiki/_external/`，手工維護 symlink。

### 安全護欄

- **Agent 只讀**：配置 `.claude/settings.json` 確保 AI agent 無法修改 symlink 或在 `_external` 下寫入。
- **Dead-link 檢查**：定期執行 lint 檢查，發現失效連結即時修復。
- **版本控制**：KNOWLEDGE_REGISTRY.md 應納入 Git，記錄各子專案的最新同步日期。

### 故障排除

| 症狀 | 原因 | 解決方案 |
|---|---|---|
| `ln: cannot create symbolic link: File exists` | 目標資料夾已存在 | 刪除舊資料夾或用不同的 short name |
| symlink 顯示 `→ [broken]` | 目標路徑不存在或路徑錯誤 | 驗證 `~/mops_dbs/docs` 存在；用 `readlink -f` 確認完整路徑 |
| 編輯器顯示 symlink 内容為空 | 編輯器不支援 symlink 追蹤 | 用終端機或支援 symlink 的編輯器（VS Code, Obsidian） |
| Lint 工具無法讀取 symlink | Lint 工具配置不支援跟進 symlink | 更新 lint 工具設定或在檢查命令加 `-L` 標籤 (e.g., `find -L wiki/_external`) |