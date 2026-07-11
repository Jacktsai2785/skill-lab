---
name: personal-knowledge-wiki
slug: personal-knowledge-wiki
description: "個人知識庫工作流：raw（原始）→ inbox（清單）→ wiki（互聯）三層架構，包含 consume/link/lint/digest 四大操作模板。TRIGGER when: 建立新筆記環境、建立跨多 vault 的知識管理系統、移轉 jk-nb 工作流到新專案。"
version: 1.0.0
tags:
  - knowledge-management
  - markdown
  - personal-wiki
  - workflow
  - meta
languages: all
---

## Overview

personal-knowledge-wiki 是一套完整的個人知識庫系統，用於管理和連接分散的筆記資料。它採用三層架構：

- **raw/**：不可變的原始資料層，存放未經加工的內容（剪貼簿摘錄、網路文章、會議記錄等）
- **inbox/**：暫存清單層，記錄待處理和已處理的項目（使用刪除線而非刪除）
- **wiki/**：互聯知識庫，經過整理、連結和演化的最終形式

核心提供四個操作的 prompt 模板和執行指南：

1. **consume**：攝入原始資料，標準化格式
2. **link**：在 wiki 中建立跨文件的概念連結
3. **lint**：檢查結構一致性和連結完整性
4. **digest**：從 wiki 生成聚合視圖（索引、主題地圖、月度回顧）

## 何時使用

- **建立新的個人筆記環境**：已有 raw 資料和 inbox 流程的想法，需要一套現成的工作流框架
- **跨多個 vault 的知識管理**：需要在 Obsidian、自建系統或多個工具間實現一致的知識架構
- **移轉 jk-nb 系統**：已在其他專案中成功運行，現在要在新環境（客戶筆電、新筆記專案）重建
- **構建組織知識庫**：從個人系統擴展到團隊知識管理

## 執行步驟或模式

### 1. 初始化目錄結構

```
knowledge-vault/
├── raw/                          # 不可變原始層
│   ├── articles/
│   ├── clips/
│   └── captures/
├── inbox/
│   └── INBOX.md                 # 待處理項目清單
└── wiki/                        # 可編輯的互聯知識庫
    ├── index.md
    ├── topics/
    ├── people/
    └── references/
```

raw/ 中的檔案一旦建立，**不應再修改**。新版本應存為新檔案（如加時間戳或版本號）。

### 2. Frontmatter Schema

所有 wiki 中的檔案遵循此 frontmatter：

```yaml
---
title: [標題]
tags: [comma, separated, tags]
created: YYYY-MM-DD
updated: YYYY-MM-DD
related:
  - "[[相關檔案1]]"
  - "[[相關檔案2]]"
status: active|archived|draft
---
```

raw/ 中的檔案使用最小化 frontmatter：

```yaml
---
source: [來源 URL / 工具 / 日期]
captured: YYYY-MM-DD
---
```

### 3. 命名規則

- **wiki/ 主檔案**：`PascalCase-noun.md`（如 `KnowledgeManagement.md`、`ReflectionPractice.md`）
- **raw/ 檔案**：`YYYY-MM-DD-slug.md` 或 `source-slug.md`（如 `2026-06-13-article-ai-agents.md`）
- **inbox 條目**：統一在 INBOX.md 中，不建立個別檔案

### 4. Consume 操作

**何時執行**：新資料進入系統時（剪貼簿、文章、筆記、會議記錄）

**Prompt 模板**：

```
你是知識庫管理助手。我要將以下原始資料 consume（攝入）到個人知識庫。

原始資料：
[貼上原始內容]

執行步驟：
1. 檢查內容完整性，是否有缺少的上下文
2. 提取核心觀點和關鍵詞（3-5 個）
3. 建議在 raw/ 中的檔名（遵循 YYYY-MM-DD-slug.md）
4. 生成標準化的 frontmatter（source、captured）
5. 若內容多於 300 字，建議拆分策略
6. 產出：完整的 raw/ 檔案内容

不要修改原始內容的措辭，只補充 frontmatter 和檔名。
```

**執行流程**：
1. 準備原始內容
2. 用上述 prompt 呼叫 Claude
3. 將結果存為 `raw/YYYY-MM-DD-slug.md`
4. 在 inbox/INBOX.md 中新增一行：`- [ ] [consume] raw/YYYY-MM-DD-slug.md —— [簡短描述]`

### 5. Link 操作

**何時執行**：定期整理 inbox、或完成某個 wiki 檔案時

**Prompt 模板**：

```
我正在整理個人知識庫的 wiki/ 資料夾。目標是在相關概念間建立相互連結。

現有 wiki 檔案清單：
[列出所有 wiki/ 檔案名稱和 title]

待連結的新檔案：
標題：[檔案名稱]
內容摘要：[核心觀點]

執行步驟：
1. 掃描現有檔案，找出語意相關的檔案（3-5 個最相關的）
2. 為每個相關檔案說明連結理由（一句話）
3. 在新檔案的 frontmatter 中補充 related: 清單
4. 建議在新檔案正文中插入 [[FileName]] 雙括號連結的位置和措辭
5. 產出：更新後的新檔案内容（含 frontmatter 和主文插入點）

格式：產出 markdown，可直接複製到檔案。
```

**執行流程**：
1. 新增或編輯 wiki/ 中的檔案
2. 用上述 prompt 呼叫 Claude，提供已有的檔案列表
3. 更新檔案的 related 欄位和正文連結
4. 標記 inbox 中對應行為完成：`- [x] [link] wiki/FileName.md`

### 6. Lint 操作

**何時執行**：每週一次、或重組時，檢查知識庫結構完整性

**Prompt 模板**：

```
對我的個人知識庫進行結構檢查（lint）。

wiki/ 目錄結構和所有檔案 frontmatter：
[執行此命令的輸出：find wiki/ -name "*.md" | xargs head -20]

執行步驟：
1. 檢查每個檔案是否有完整的 frontmatter（title、tags、created、updated、status）
2. 檢查 related 連結是否指向存在的檔案
3. 找出孤立的檔案（status: active 但沒有任何入連結的檔案）
4. 檢查 tags 是否一致（拼寫、複數形態）
5. 檢查是否有過期檔案（updated 距今超過 6 個月且 status 未標記為 archived）
6. 產出：問題清單，每項包含檔名、問題類型、修復建議

格式：以 markdown table 列出。
```

**執行流程**：
1. 在知識庫根目錄執行 lint
2. 用上述 prompt 呼叫 Claude
3. 根據清單逐項修復（可手動或再次呼叫修復 prompt）
4. 在 inbox 中記錄：`- [x] [lint] YYYY-MM-DD —— N 項修復`

### 7. Digest 操作

**何時執行**：每月末、季度末、年度末；或定期生成聚合視圖時

**Prompt 模板**：

```
從我的個人知識庫生成聚合摘要（digest）。

範圍：[本月 / 本季 / 本年] 更新的 wiki 檔案

檔案清單及 updated 日期：
[執行此命令的輸出：find wiki/ -name "*.md" -exec grep -l "updated: YYYY-MM" {} \; | xargs -I {} sh -c 'echo "{}"; head -10 "{}"']

執行步驟：
1. 按主題（tags）分類新增或更新的檔案
2. 為每個主題寫 30-50 字的聚合摘要，說明該月份的進展和新連結
3. 生成「主題索引」：列出本期涉及的所有 tag 及其檔案數
4. 生成「連結地圖」：找出最多被參考的檔案（連結度最高）
5. 產出：一份 digest.md，包含以上 4 個小節

格式：markdown，可存為 wiki/digest/Digest-2026-06.md
```

**執行流程**：
1. 在月末、季末或年末執行
2. 用上述 prompt 呼叫 Claude
3. 存檔至 `wiki/digest/Digest-YYYY-MM.md`
4. 在 INBOX.md 記錄：`- [x] [digest] Digest-2026-06.md`

### 8. Inbox 流程

INBOX.md 是整個系統的操作日誌。格式：

```markdown
# Inbox — 2026-06

## 待處理

- [ ] [consume] raw/2026-06-13-article-xyz.md —— 新文章摘錄
- [ ] [link] wiki/KnowledgeManagement.md —— 補充連結

## 已處理

- [x] ~~[consume] raw/2026-06-12-clip-abc.md~~ —— 新剪貼
- [x] ~~[link] wiki/ReflectionPractice.md~~ —— 建立跨檔連結
- [x] ~~[lint] 2026-06-10~~ —— 修復 3 項格式問題

## 檔案變更統計

- 本月新增 wiki 檔案：5
- 本月更新檔案：12
- raw 資料總量：48 項
- 平均連結度（related 連結數 / 檔案數）：2.3
```

**關鍵規則**：
- 完成任務時，使用**刪除線** `~~[操作] 檔案~~` 而非刪除，保留完整的操作歷史
- 每月初新增一個 ## YYYY-MM 區段
- 月底執行一次 digest，並記錄變更統計

## 注意事項

1. **raw/ 的不可變性**：raw 資料夾中的檔案代表「事實記錄」。若發現錯誤或需要新版本，應建立新檔案而非修改原檔。這樣可保證完整的變更歷史和溯源。

2. **wiki/ 的可編輯性**：wiki 資料夾的檔案是「工作產物」，可以隨時修改、重新組織、刪除。updated frontmatter 應在每次編輯後更新。

3. **Inbox 的防刪除機制**：使用刪除線而非刪除行，可以保留完整的操作歷史（何時 consume、link、lint 的）、支持 digest 時回顧月度活動、防止誤刪重要上下文。

4. **related 連結不要過多**：每個檔案的 related 欄位建議維持在 3-7 個連結。超過 10 個表示該檔案定位不清或應拆分。

5. **Tag 命名一致性**：建立 tag 時遵循單數形態（如 `knowledge-management` 而非 `knowledge-managements`）。定期執行 lint 檢查拼寫和重複。

6. **Status 欄位的用途**：`active` 為正在維護和演化的檔案；`draft` 為初稿或不確定納入 wiki；`archived` 為過時但保留供參考，不在月度 digest 中統計。

7. **跨 Vault 同步**：若在多個筆記工具間使用（如 Obsidian + GitLab），raw/ 只進行內容同步（無衝突），wiki/ 在單一工具編輯、其他工具只讀，透過 Git 或 Syncthing 等工具同步檔案，避免同時編輯同一個 wiki 檔案。

8. **Consume 的粒度選擇**：短文章（<500 字）整份作為一個 raw 檔案；長文章（>500 字）按邏輯段落拆分各為一個 raw 檔案，並在 inbox 記錄關聯。

9. **效能和規模**：wiki 檔案數 < 500 時系統運作流暢；達到 1000+ 時考慮按主題分資料夾（如 `wiki/technology/`、`wiki/business/`）；定期執行 lint 和 digest 保持系統健康。

10. **版本控制**：若用 Git 管理，`.gitignore` 排除 `.DS_Store`、`.obsidian/` 等工具檔案；raw/ 和 wiki/ 都應納入版控；每月執行一次 `git log --oneline` 檢查修改頻率。