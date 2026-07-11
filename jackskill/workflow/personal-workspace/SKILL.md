---
name: personal-workspace
description: 以 Obsidian 風格自動建立個人筆記庫結構、決策記錄、面試紀錄等，含 README 索引與 archive 機制。TRIGGER when: 整理個人資料夾、建立知識庫、歸檔筆記時
when_to_use: 建立新的個人知識庫、整理散亂筆記、建立決策記錄系統、面試紀錄歸檔、或定期整理備份
version: 1.0.0
tags:
  - workspace
  - knowledge-management
  - personal-productivity
  - obsidian
  - note-taking
languages: all
---

## Overview

個人知識庫的長期維護需要一套結構化系統——能自動建立資料夾層級、生成索引、定期歸檔、並保持 backlink 可追溯性。本 skill 提供 Obsidian 風格的個人工作區組織框架，自動化初始化與運維。

與傳統個人資料夾的差異：
- **結構化**：固定分類（筆記、決策、面試、會議紀錄）
- **可尋**：README 層級索引 + 前言 metadata
- **易清理**：自動 archive 機制（按日期或狀態標記）
- **可備份**：Git 整合或定期 ZIP 包

## 何時使用

1. **建立新的個人知識庫**
   - 從零開始組織個人筆記與決策記錄
   - 例：加入新公司、轉換角色、或重整個人秘書處

2. **整理散亂的筆記**
   - 已有一堆 .md、.txt 檔案分散在不同資料夾
   - 需要統一命名規範、添加前言、建立索引

3. **建立決策/會議紀錄系統**
   - 面試紀錄、1:1 note、project retrospective
   - 需要按日期或專案分類，並自動歸檔舊紀錄

4. **定期維護與備份**
   - 每季/每年整理一次，將舊紀錄移至 archive
   - 生成統計與索引更新

## 執行步驟與模式

### 1. 初始化資料夾結構

```
~/my-workspace/
├── README.md                 # 主索引
├── .metadata/               # 系統檔案
│   ├── vault-config.json   # vault 設定
│   └── archive-log.json    # 歸檔記錄
├── 📝-notes/               # 長期筆記
│   ├── README.md
│   ├── topics/
│   └── templates/
├── 🎯-decisions/           # 決策記錄
│   ├── README.md
│   ├── 2026-05/
│   └── 2026-06/
├── 👤-interviews/          # 面試紀錄
│   ├── README.md
│   ├── by-company/
│   └── by-role/
├── 📅-meetings/            # 會議紀錄
│   ├── README.md
│   └── by-date/
└── 📦-archive/             # 歸檔區
    ├── 2025-notes/
    └── 2025-decisions/
```

建立指令：
```bash
mkdir -p ~/my-workspace/{📝-notes,🎯-decisions,👤-interviews,📅-meetings}/{README,templates}
mkdir -p ~/my-workspace/{📝-notes/topics,🎯-decisions,👤-interviews/{by-company,by-role},📅-meetings/by-date}
mkdir -p ~/my-workspace/{📦-archive,.metadata}
```

### 2. 生成主 README（vault 索引）

主 README 應包含：
- vault 用途與更新頻率
- 各分類的快速連結
- 最近更新列表
- archive 週期說明

示例模板（在 `~/my-workspace/README.md`）：
```
# Personal Workspace

**Last synced**: 2026-06-13 | **Vault size**: TODO (will auto-fill)

## 快速導航

- **📝 [筆記庫](📝-notes/README.md)** — 主題知識、學習紀錄、技術筆記
- **🎯 [決策記錄](🎯-decisions/README.md)** — 重要決策、trade-off 分析、OKR
- **👤 [面試紀錄](👤-interviews/README.md)** — 面試經驗、公司評估、薪資水準
- **📅 [會議紀錄](📅-meetings/README.md)** — 1:1、retrospective、project sync

## 最近活動

| 日期 | 類別 | 標題 | 狀態 |
|------|------|------|------|
| 2026-06-13 | 決策 | 轉職評估：A 公司 vs B 公司 | ✅ completed |
| 2026-06-10 | 面試 | Google 面試紀錄 — Round 2 | 🔄 pending-followup |

## 歸檔政策

- **筆記**：無自動歸檔（backlink 優先）
- **決策紀錄**：超過 1 年自動移至 archive/
- **面試紀錄**：status=rejected 或 >2 年自動歸檔
- **會議紀錄**：每季末整理，舊會議按年份分類

查看 [archive](📦-archive/) 或執行 `python archive-scan.py` 檢視歸檔狀態。
```

### 3. 各分類的 README 模板

**筆記庫 (📝-notes/README.md)**：
```
# 📝 筆記庫

主要收集長期知識與學習紀錄，以主題分類。支援 bidirectional link（例：[[Ruby]] 語言筆記與決策記錄互連）。

## 主題列表

| 主題 | 最後更新 | 筆記數 |
|------|---------|-------|
| Ruby | 2026-05-20 | 8 |
| Database | 2026-06-01 | 12 |

## 新增筆記

1. 在 `topics/` 下建立 `YYYY-MM-DD-title.md`
2. 前言包含：topic tag、difficulty、status
3. 內容範例見 `templates/note-template.md`
```

**決策記錄 (🎯-decisions/README.md)**：
```
# 🎯 決策記錄

重要決策、trade-off 分析、career 轉折點。

## 2026 年決策

| 日期 | 標題 | 狀態 | outcome |
|------|------|------|---------|
| 2026-06-13 | 轉職方向選擇 | completed | 選 A 公司 |

## 狀態說明

- `in-progress` — 正評估中
- `completed` — 已決策
- `on-hold` — 暫停
- `revisit` — 需重新評估
```

**面試紀錄 (👤-interviews/README.md)**：
```
# 👤 面試紀錄

## 按公司分類

- [Google](by-company/google.md)
- [Meta](by-company/meta.md)

## 按職位分類

- [Senior Engineer](by-role/senior-engineer.md)
- [Staff Engineer](by-role/staff-engineer.md)

## 統計

- 總面試數：12
- 通過率：33%
- 最常失敗環節：System Design
```

### 4. 檔案前言規範（YAML frontmatter）

所有筆記檔案應包含：
```yaml
---
title: "筆記標題"
date: 2026-06-13
category: notes          # notes | decision | interview | meeting
status: active           # active | archived | draft | completed
tags: [tag1, tag2]
links: [[related-note]]  # bidirectional backlinks
---

# 標題

內容開始...
```

### 5. Archive 自動化

建立 `~/.my-workspace/.metadata/archive.py`：
```python
import os
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

CONFIG = {
    "notes": {"auto_archive": False},
    "decisions": {"auto_archive": True, "age_days": 365},
    "interviews": {"auto_archive": True, "status": ["rejected", "no_response"]},
    "meetings": {"auto_archive": True, "age_days": 180}
}

def archive_by_status(source_dir, target_dir, status_list):
    """根據狀態標記歸檔"""
    os.makedirs(target_dir, exist_ok=True)
    for file in Path(source_dir).glob("*.md"):
        with open(file, "r") as f:
            content = f.read()
            for status in status_list:
                if f"status: {status}" in content:
                    shutil.move(str(file), os.path.join(target_dir, file.name))
                    print(f"Archived: {file.name}")
                    break

def archive_by_age(source_dir, target_dir, days):
    """根據日期歸檔"""
    os.makedirs(target_dir, exist_ok=True)
    cutoff = datetime.now() - timedelta(days=days)
    for file in Path(source_dir).glob("*.md"):
        file_date = datetime.fromtimestamp(os.path.getmtime(file))
        if file_date < cutoff:
            shutil.move(str(file), os.path.join(target_dir, file.name))
            print(f"Archived: {file.name}")

# 執行歸檔
archive_by_age("./🎯-decisions/", "./📦-archive/decisions/", 365)
archive_by_status("./👤-interviews/", "./📦-archive/interviews/", ["rejected"])
```

執行：
```bash
cd ~/my-workspace
python .metadata/archive.py
```

### 6. Git 整合（可選但推薦）

在 `~/my-workspace/` 初始化 git：
```bash
cd ~/my-workspace
git init
cat > .gitignore << 'EOF'
.metadata/*.log
.DS_Store
*.swp
EOF
git add .
git commit -m "Initialize personal workspace vault"
```

定期自動提交（在 cron 或 systemd timer）：
```bash
cd ~/my-workspace && git add -A && git commit -m "Workspace sync — $(date +%Y-%m-%d)" 2>/dev/null || true
```

## 注意事項

1. **檔案命名規範**
   - 使用 ISO 日期前綴：`YYYY-MM-DD-title.md`
   - emoji 分類名稱在不同作業系統可能異常，推薦用 ASCII 替代：`notes/`, `decisions/` 等
   - 避免空格，使用連字號：`my-long-title.md`

2. **Backlink 注意**
   - 使用 `[[note-title]]` 參照其他檔案
   - Obsidian 或 logseq 可自動解析；純文本需搭配外部工具（如 obsidian.md 的 web 版或自製腳本）

3. **備份與同步**
   - Git 備份：定期 push 至私有 GitHub repo（務必設為 private）
   - Cloud 同步：若使用 iCloud/OneDrive，避免與 Git 同時使用（會造成衝突）
   - 本地定期備份：`tar czf backup-$(date +%Y%m%d).tar.gz ~/my-workspace/`

4. **泛用性考量**
   - 本 skill 目前基於個人秘書處場景（筆記、決策、面試、會議）
   - 若用於團隊知識庫，需額外的 collaborative lock、權限管理
   - 跨機構應用需驗證檔案編碼（推薦 UTF-8）與路徑相容性

5. **已知限制**
   - Archive 腳本假設 Python 3.8+
   - Emoji 資料夾在 Windows cmd 可能不支援（改用 ASCII 替代）
   - 大型 vault（>1000 檔案）建議增加索引策略或分散至子 vault