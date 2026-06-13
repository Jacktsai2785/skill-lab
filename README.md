# skill-lab

我（Jack）自己原創的 Claude Code skill 開發庫，與 `rivendell`（朋友的 repo）獨立。
透過 `deploy.sh` symlink 進 `~/.claude/skills/`，所有專案全域可用。

## Skills（17）

### workflow/
| Skill | 說明 |
|---|---|
| `task-brief` | 四階段判斷（思考/探索/決定/執行）+ 五欄位任務定義 brief |
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

### meta/
| Skill | 說明 |
|---|---|
| `github-skill-installer` | 從第三方 GitHub 安裝單一 skill 到本地/全域 |

### backend/
| Skill | 說明 |
|---|---|
| `scraping-frontdoor-vs-backdoor` | 爬蟲前台/後台策略決策樹 |
| `pdf-ocr-routing` | PDF 類型偵測 → 文字抽取/OCR 路由 |

## 部署

```bash
./deploy.sh        # 把所有 skill symlink 進 ~/.claude/skills/
```

安全護欄：若 `~/.claude/skills/<name>` 已是真實目錄（非 symlink），`deploy.sh` 會跳過並警告，避免遮蔽。

## 設計來源

`task-brief` 的框架整理自 YouTube「你不是不會寫 Prompt，是不會定義任務」：四階段（思考/探索/決定/執行）各餵 AI 不同的東西，執行階段用五欄位（目標/背景/素材/邊界/完成定義）定義任務。

其餘 16 個為從 rivendell 個人原創層搬入的通用工程 skill（2026-06-13）。
