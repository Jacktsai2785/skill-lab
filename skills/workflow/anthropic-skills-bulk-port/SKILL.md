---
name: anthropic-skills-bulk-port
description: |
  TRIGGER when: 使用者說「幫我把 anthropic 的 skill 都安裝好」「從 X repo 移植 skills」「批次安裝 skill」「把這個 skills 倉庫合進來」等，需要從外部 GitHub skills 倉庫（特別是 anthropics/skills）批次移植 SKILL.md 檔案到本地 rivendell 目錄結構，含格式調整、衝突偵測、README 同步。
version: 1.0.0
tags:
  - meta
  - skills-infrastructure
  - automation
  - batch-operation
languages: all
---

## Overview

`anthropic-skills-bulk-port` 是一個 meta-level skill，用於從外部 GitHub skills 倉庫（特別是官方的 `anthropics/skills`，也支援任意 skills 集合）批次下載、解析、並移植多個 SKILL.md 檔案到本地 rivendell 目錄結構。

主要價值：
- **批量移植**：一次性從官方倉庫取得多個 skills，而非逐個手工複製
- **格式轉換**：自動檢查並調整 frontmatter、觸發條件等，確保符合本地 rivendell 規範
- **衝突偵測**：識別本地已存在的 slug，提示覆蓋或跳過決策
- **目錄分類**：根據 skill 類型（backend、workflow、meta）自動歸位到正確子目錄
- **文檔同步**：移植完成後自動更新 README.md 中的 Skills Catalog 表格

適用於：官方 anthropic 官方新版本發布、從第三方團隊 fork 的 skills 倉庫、內部 shared skills collection 統一遷移。

## 何時使用

1. **官方更新批量合入**  
   Anthropic 官方發布新版本或大批 skills，需要一次性把所有新增 skills 併入本地倉庫。

2. **跨團隊 skills 倉庫合併**  
   多個團隊各有一份 skills 集合（例如行銷團隊、工程團隊各自的 fork），需要統一合進來。

3. **快速初始化新機器**  
   新建立的機器或新開發者需要快速把整個 skills 倉庫一次性複製到本地。

4. **版本升級遷移**  
   skills 倉庫重構或重命名，需要批量適配本地目錄結構。

## 執行步驟

### 1. 確定源倉庫與認證

確保可以存取源倉庫（無論是公開或需要 GitHub token）：

```bash
# 公開倉庫（anthropics/skills）
SOURCE_REPO="github.com/anthropics/skills"
SOURCE_DIR="skills"

# 或指定其他 fork
SOURCE_REPO="github.com/your-org/skills"
SOURCE_DIR="skills"

# 驗證存取權限
gh repo view $SOURCE_REPO > /dev/null && echo "✓ 可存取" || echo "✗ 無權限"
```

### 2. 列舉候選 SKILL.md 檔案

遠端抓取源倉庫中所有 SKILL.md，解析 frontmatter 提取 name / slug：

```bash
# 克隆或更新臨時目錄
mkdir -p /tmp/skills-import
cd /tmp/skills-import
git clone --depth 1 https://$SOURCE_REPO.git src 2>/dev/null || (cd src && git pull)

# 列舉所有 SKILL.md，提取 name 與分類
find src/skills -name "SKILL.md" -type f | while read skill_file; do
  category=$(echo $skill_file | cut -d'/' -f3)  # 例如 "backend", "workflow"
  slug=$(grep "^name:" "$skill_file" | head -1 | sed 's/^name: //' | xargs)
  echo "$category | $slug | $skill_file"
done | tee candidates.txt
```

### 3. 檢查衝突與決策

遍歷候選列表，對標本地已有的 skills：

```bash
while IFS=' | ' read category slug remote_file; do
  local_path="./skills/$category/$slug/SKILL.md"
  
  if [ -f "$local_path" ]; then
    # 檢查版本
    remote_version=$(grep "^version:" "$remote_file" | cut -d' ' -f2)
    local_version=$(grep "^version:" "$local_path" | cut -d' ' -f2)
    
    echo "⚠️  衝突: $slug"
    echo "  本地版本: $local_version"
    echo "  遠端版本: $remote_version"
    # 決策：覆蓋 (Y/n) 或標記為 skip
  else
    echo "✓ $category / $slug — 新增"
  fi
done < candidates.txt
```

### 4. 批量複製並格式調整

根據衝突決策，複製 SKILL.md 到本地目錄，並驗證 frontmatter 格式：

```bash
cat candidates.txt | while IFS=' | ' read category slug remote_file; do
  target_dir="./skills/$category/$slug"
  
  # 創建目錄結構
  mkdir -p "$target_dir"
  
  # 複製 SKILL.md
  cp "$remote_file" "$target_dir/SKILL.md"
  
  # 驗證 frontmatter 格式（確保包含 name, description, version, tags, languages）
  # 如果缺少欄位，自動補充預設值
  if ! grep -q "^languages:" "$target_dir/SKILL.md"; then
    # 在 version 行後插入 languages: all
    sed -i '/^version:/a languages: all' "$target_dir/SKILL.md"
  fi
  
  echo "✓ 複製: $target_dir/SKILL.md"
done
```

### 5. 同步 README.md

移植完成後，運行本地更新 README.md Skills Catalog 表格：

```bash
# 重新掃描本地 skills，重構 Skills Catalog
# （呼叫現有的 README 同步邏輯，或直接編輯）
node ./scripts/sync-skills-readme.js

# 或手工更新（如 README 未有自動化機制）
# 1. 計算新的 skill 數量
skill_count=$(find ./skills -name "SKILL.md" | wc -l)

# 2. 編輯 README.md，更新表格行數、分類統計
# Skills Catalog (NN skills)：NN 更新為新計數
```

### 6. 驗證與提交

完成後驗證結構完整性：

```bash
# 確認所有複製的 SKILL.md 都有有效 frontmatter
for f in ./skills/*/*/SKILL.md; do
  if ! head -20 "$f" | grep -q "^name:"; then
    echo "✗ 缺少 frontmatter: $f"
  fi
done

# 執行本地測試（如有 CI 檢查）
npm run lint  # 或相應的驗證命令

# 提交變更
git add -A
git commit -m "feat(skills): anthropic skills 批量移植 — $skill_count skills"
```

## 注意事項

### 衝突處理

- **不推薦無條件覆蓋**：批量移植時應逐個確認衝突決策，特別是本地有修改的 skills
- **版本號參考**：如本地版本 > 遠端，考慮保留本地版本；反之檢查遠端是否有重要更新
- **保留 changelog**：若覆蓋本地 skill，先備份舊版本，記錄變更歷史

### 格式相容性

- **frontmatter 差異**：外部倉庫的 SKILL.md 可能使用略異的欄位名（如 `author` vs `owner`），複製後需驗證符合 rivendell 規範
- **TRIGGER 格式**：確保 `description` 欄位含有明確的 TRIGGER when: 段落，便於後續 skill routing
- **languages 欄位**：如源倉庫未指定，預設為 `all`

### 目錄歸類

- **分類邏輯**：源倉庫的目錄結構（skills/backend/ vs skills/workflow/）應與本地一致；如不一致，需手工調整
- **meta skills**：與 skill-creator、skill-scout 同類的基礎設施 skills，應納入 `skills/meta/` 或頂層 `skills/` 目錄（取決於本地慣例）

### 效能考慮

- **大規模倉庫**：若源倉庫超過 100+ skills，首次 clone 可能耗時，考慮使用 `--depth 1` 淺複製或直接下載 tarball
- **網路中斷恢復**：批量複製中斷可重新執行，已複製的 skills 可透過 checksum 驗證跳過重複

### 依賴與版本鎖定

- **跨版本相容**：本地 skills 可能依賴特定版本的 Claude API 或其他 SDK；批量移植後應驗證 package.json / requirements 不產生版本衝突
- **更新頻率**：建議定期（如季度）檢查源倉庫更新，而非一次性批量同步

## 範例工作流程

典型的使用場景（官方 anthropic/skills 更新）：

```bash
# 1. 檢查本地狀態
cd ~/rivendell
git status

# 2. 啟動 skill — anthropic-skills-bulk-port
sk anthropic-skills-bulk-port

# 3. 執行步驟
# - 源倉庫: github.com/anthropics/skills
# - 臨時目錄: /tmp/skills-import
# - 候選篩選: 過濾 deprecated 或 experimental skills
# - 衝突檢查: 本地 audio-transcription v1.2.0 vs 遠端 v1.3.0 → 詢問覆蓋
# - 批量複製: 複製 12 個新 skills 到 skills/backend/ 與 skills/workflow/
# - README 更新: Skills Catalog (156 skills) → (168 skills)

# 4. 驗證
npm run lint
git diff skills/

# 5. 提交
git commit -m "feat(skills): anthropic 官方 skills 更新 — 新增 12 skills"
```

---

此 skill 應在使用者明確要求「批次安裝」或「從倉庫移植 skills」時觸發，而非處理單個 skill 新增（該由 skill-creator 處理）。