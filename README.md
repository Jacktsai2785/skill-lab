# skill-lab

我（Jack）自己原創的 Claude Code skill 開發庫，與 `rivendell`（朋友的 repo）獨立。
透過 `deploy.sh` symlink 進 `~/.claude/skills/`，所有專案全域可用。

## Skills

| Skill | 觸發 | 說明 |
|---|---|---|
| `task-brief` | 自動 + `/task-brief` | 把模糊交辦翻譯成「四階段判斷 + 五欄位 brief」的任務定義；也能稽核既有 prompt 缺哪一欄 |

## 部署

```bash
./deploy.sh        # 把所有 skill symlink 進 ~/.claude/skills/
```

安全護欄：若 `~/.claude/skills/<name>` 已是真實目錄（非 symlink），`deploy.sh` 會跳過並警告，避免遮蔽。

## 設計來源

`task-brief` 的框架整理自 YouTube「你不是不會寫 Prompt，是不會定義任務」：四階段（思考 / 探索 / 決定 / 執行）各餵 AI 不同的東西，執行階段用五欄位（目標 / 背景 / 素材 / 邊界 / 完成定義）定義任務。
