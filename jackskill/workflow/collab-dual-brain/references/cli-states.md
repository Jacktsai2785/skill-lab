# collab CLI 完整參考

## 指令表

| 指令 | 用途 |
|------|------|
| `collab run -p "..." [flags]` | 啟動新 run（見下方 flags） |
| `collab init --output x.json` | 產生可版本化的 brief 模板 |
| `collab status RUN_ID` | 狀態 + 預算用量（cycle/revisions/tokens/+cache） |
| `collab issues RUN_ID [--open-only]` | canonical issues 清單 |
| `collab answer RUN_ID CARD_ID --choice OPTION_ID` | 回答決策卡並續跑 |
| `collab resume RUN_ID` | 從暫停恢復；自動沿用原 run 的 fake／real profile |
| `collab extend-budget RUN_ID --tokens N [--cycles N] [--revisions N] [--active-seconds N] [--final-audit-reopens N]` | 追加預算（只增不減） |
| `collab cancel RUN_ID` | 取消（終態、有 audit） |
| `collab report RUN_ID --format md\|json\|html` | 報告；JSON 可讀 pending cards，HTML 含渲染圖且目前需網路 |
| `collab audit RUN_ID` | 決定性事件時間軸 |
| `collab calls RUN_ID` | 模型呼叫 journal（狀態/attempts/committed） |
| `collab ui [--port 8787]` | 本機 dashboard |

### run 的 flags

- `-p` 題目（含背景事實）
- `--hard-constraint` / `--soft-constraint`（可重複）
- `--hard-ac` / `--soft-ac`（可重複，hard 至少一條）
- `--non-goal`（可重複；local-only 專案排除伺服器/網路安全）
- `--artifact 路徑`（素材檔）
- `--brief x.json`（取代 -p 與逐條 flags）
- `--max-tokens N`（覆寫 150k 預設；真實 run 提高 ceiling 前先取得同意）
- `--fake`（零成本假模型，測流程用）
- `--data-dir`（預設 ~/.collab-orchestrator）

## Run 狀態 → 該做什麼

| 狀態 | 意義 | 動作 |
|------|------|------|
| `completed` | 全部驗收通過 | 交付報告 |
| `completed_with_unverified_hard_ac` | 完成但有 hard AC 設計審查證明不了 | 交付 + 醒目標示未驗證項與測試建議 |
| `awaiting_user_facts` | brief 缺少會改變方向的事實 | 問清事實；目前 CLI 無補寫既有 brief 命令，取得重開同意後 cancel 舊 run，以完整 brief 開新 run |
| `awaiting_user_decision` | 有決策卡等使用者 | 用 JSON report 取回全部 pending cards，整批轉達；取得選擇後逐張 `answer` 並重查狀態 |
| `paused_budget_exhausted` | 某預算維度觸頂 | 提出 exhausted dimensions、最小追加量與目前 tokens；使用者同意後 `extend-budget` → `resume` |
| `paused_agent_unavailable` | CLI 呼叫失敗（retry 用盡） | `resume` 重試一次；再失敗回報使用者（可能是登入/網路問題） |
| `paused_waiting_user` | 等使用者回覆逾時 | 查看 `paused_from`；decision：`resume` 後 `answer`；facts：取得事實後重建 brief／新 run |
| `escalated_for_redesign` | 使用者選了 redesign | 依新前提開新 run |
| `cancelled_by_user` | 已取消 | — |
| `failed_preflight` | 前置檢查不過（CLI 缺/未登入） | 修環境後開新 run |
| `failed_integrity_check` | ledger/artifact 損毀 | 不可恢復；查 audit、開新 run |

## 授權邊界

- 使用者明確要求雙腦協調，只授權一次預設 budget 的 run。
- `--max-tokens` 高於預設、任何 `extend-budget`、取消 run 或依 redesign
  開新 run，都要取得對應的明確指示。
- `resume`、一次 agent-unavailable retry、`status`、`issues`、`report`、
  `audit`、`calls` 屬於既有 run 的正常操作，不需再次確認。

## 內部流程（回答使用者提問用）

```
雙盲提案（互不可見）→ 匿名交叉評審（有 evidence 才算 finding）
→ canonical issues → 決定性裁決 → targeted revision（作者修、對方驗證）
→ 收斂 → synthesis（依 ledger 折衷）→ fresh-context 紅隊終審
→ completeness gate → 報告 + decision log + 殘留風險
```

- 必解問題（escalation blocker）迴圈到雙腦同意，預算只是暫停點
- 真僵局（reopen 超限）→ 雙 fresh judge，同向且過 evidence gate 才採納，
  否則決策卡
- 模型不能自稱 accepted_risk、不能裁決 not_satisfied——只有使用者/證據能
