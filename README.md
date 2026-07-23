# skill-lab

我（Jack）自己原創的 Claude Code skill 開發庫，與 `rivendell`（朋友的 repo）獨立。
透過 `deploy.sh` symlink 進 `~/.claude/skills/`，所有專案全域可用。

## Skills（21）

### workflow/
| Skill | 說明 |
|---|---|
| `task-brief` | 四階段判斷（思考/探索/決定/執行）+ 五欄位任務定義 brief |
| `collab-dual-brain` | 關鍵字觸發雙腦協調：Claude×Codex 雙盲提案互審，產出含圖設計報告（呼叫 collab CLI） |
| `dev-port-conflict-fix` | dev server port 衝突偵測與修復 |
| `multi-project-port-replan` | 多專案 port 盤點、衝突診斷、重新規劃 |
| `vscode-wsl-port-forwarding-debug` | WSL/VSCode PORTS 面板轉發除錯 |
| `react-fab-search-pattern` | React 浮動搜尋組件（typed endpoint + 鍵盤導航） |
| `hierarchy-breadcrumb-from-flat-category` | 扁平分類 key → 階層麵包屑 |
| `excel-ssot-display-order-sync` | Excel 顯示順序 SSOT 同步 |
| `github-repo-onboard` | 上手任意 GitHub repo、產重構/遷移計畫 |
| `anthropic-skills-bulk-port` | 從外部 repo 批次移植 skill |
| `phased-spec-builder` | 依分階段 SPEC.md 建全棧 app |
| `plan-with-external-benchmarks` | 規劃時並行查 codebase + 業界標竿 |
| `cross-project-docs-symlink-bridge` | 跨專案文件橋接到主知識庫 |
| `personal-workspace` | Obsidian 風個人筆記庫結構 |
| `personal-knowledge-wiki` | raw→inbox→wiki 三層知識庫工作流 |
| `project-redteam-review` | 全專案盤點＋code↔文檔驗證＋三紅隊並行審查＋彙整最佳設計（可選套用） |
| `tw-call-memo` | 台灣企業訪談逐字稿轉投資研究 memo |
| `tw-company-identify` | 台灣公司名稱、統編與別名辨識 |

### meta/
| Skill | 說明 |
|---|---|
| `github-skill-installer` | 從第三方 GitHub 安裝單一 skill 到本地/全域 |

### backend/
| Skill | 說明 |
|---|---|
| `scraping-frontdoor-vs-backdoor` | 爬蟲前台/後台策略決策樹 |
| `pdf-ocr-routing` | PDF 類型偵測 → 文字抽取/OCR 路由 |

## Skill 撰寫架構（必遵）

本文庫同時以 Claude Code 與 Codex 可攜性為目標。範例實作：
`jackskill/workflow/project-redteam-review/`。

1. **Frontmatter**：只放 `name` 與 `description`。`description` 同時說明
   功能、觸發情境與不適用情境；長內容才使用 `>-`。
2. **SKILL.md body**：使用祈使句，保留完成任務必需的流程、判斷與護欄，
   不重複 frontmatter 的觸發說明。
3. **漸進揭露**：框架差異、長範例與領域知識按需放入 `references/`；
   SKILL.md 必須直接連結並說明何時讀取。
4. **可重複執行**：容易寫錯或反覆重造的邏輯放入 `scripts/`，實際執行
   測試；輸出模板或靜態素材放入 `assets/`。
5. **介面 metadata**：建議提供 `agents/openai.yaml`，且內容必須與
   SKILL.md 同步。

`references/`、`scripts/`、`assets/` 與 Gotchas 都是按需要建立，不放
空目錄或空章節。原則是單一職責、body 少於 500 行、避免未驗證的可執行
範例。修改後執行 Codex `skill-creator/scripts/quick_validate.py`，並
測試所有新增腳本。

## 部署

```bash
./deploy.sh        # 把所有 skill symlink 進 ~/.claude/skills/
```

安全護欄：若 `~/.claude/skills/<name>` 已是真實目錄（非 symlink），`deploy.sh` 會跳過並警告，避免遮蔽。

## 設計來源

`task-brief` 的框架整理自 YouTube「你不是不會寫 Prompt，是不會定義任務」：四階段（思考/探索/決定/執行）各餵 AI 不同的東西，執行階段用五欄位（目標/背景/素材/邊界/完成定義）定義任務。

部分通用工程 Skill 於 2026-06-13 從 rivendell 個人原創層搬入，後續
在本 repo 獨立維護。
