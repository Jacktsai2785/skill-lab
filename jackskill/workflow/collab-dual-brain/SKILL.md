---
name: collab-dual-brain
description: >-
  使用本機 collab-orchestrator 讓 Claude 與 Codex 雙盲提案、匿名交叉評審、
  issue-driven 收斂並產出決策報告。當使用者明確說「雙腦」「雙盲評審」
  「讓 Codex／Claude 也看一下」「collab run」「雙模型評審」或指定
  collab-dual-brain 時使用；重大架構或 workflow 草案完成後可以先提議，
  但取得同意前不得啟動真實 run。不要用於一般 diff review、單純畫圖、
  bug 修復、小幅重構或既有 collab run 的一般追問。
---

# collab-dual-brain — 雙腦設計協調

把設計題目交給本機的 `collab` CLI（claude-codex-orchestrator），讓 Claude 與
Codex 雙盲提案、互審收斂，回傳含 Mermaid 圖與殘留風險清單的最終報告。

## 啟動與授權

1. 使用者明確要求雙腦／雙盲／`collab run` 時，該要求視為授權啟動一次
   **預設預算**的真實 run。啟動前簡短告知：通常約 5–15 分鐘，模型成本會因
   CLI 訂閱／計價與實際收斂輪數而異；過往單次約 US$1–3，只能當參考。
2. 僅由重大設計情境推測可能需要時，先提議，取得同意才啟動。
3. 測試或示範使用 `--fake`，不呼叫模型。
4. 不要預先把 `--max-tokens` 提高到 300k。任何超過預設 150k 的初始 ceiling，
   或後續 `extend-budget`，都要先取得使用者明確同意。

## 執行步驟

### 1. 前置檢查

```bash
command -v collab
collab version
command -v claude
command -v codex
```

`collab` 不在 PATH 時，檢查
`$HOME/claude-codex-orchestrator/.venv/bin/collab`，找到後在本次流程中固定使用
該完整路徑。真實 run 還要確認 `claude` 與 `codex` CLI 存在；`--fake` 不需要。
任何一項仍缺少時，回報缺少項目與專案位置後停止，不要自行安裝或登入。

### 2. 從對話組 brief（不要另外問一輪）

從既有對話萃取，缺「會改變方案方向的關鍵事實」才問（一次問齊）：

- `-p`：設計題目（含足夠背景，對話裡已有的事實直接寫進去）
- `--hard-constraint`：不可違反的限制（每條一個 flag）
- `--hard-ac` / `--soft-ac`：驗收條件（至少一條 hard）
- `--non-goal`：明確排除的維度（local-only 專案記得排除伺服器/網路安全）

素材檔案用 `--artifact 路徑`；複雜 brief 先 `collab init --output x.json` 再
`--brief x.json`。

### 3. 背景執行並盯進度

```bash
collab run -p "..." --hard-ac "..." ...   # 用宿主的長程序機制執行
collab status RUN_ID                       # 取得 run ID 後查狀態
```

保留長程序的 session／cell ID，擷取 CLI 第一段輸出的 `run RUN_ID started`。
每 30–60 秒查一次或等待新輸出，期間向使用者提供簡短進度；不要 tight polling，
也不要對同一 run 同時發出兩個 mutation 指令。

依結束狀態處理：

| 狀態 | 動作 |
|------|------|
| `awaiting_user_facts` | 詢問缺少事實；目前 CLI 沒有補寫既有 brief 的命令，取得新事實與重開同意後 cancel 舊 run，使用完整 brief 開新 run |
| `paused_budget_exhausted` | 讀取 CLI 顯示的 exhausted dimensions，提出最小追加量、目前 tokens（含 `+cache`）與影響；**等使用者同意**後才 `extend-budget`，再 `resume` |
| `paused_agent_unavailable` | 直接 `collab resume RUN_ID` 重試一次；再失敗才回報使用者 |
| `paused_waiting_user` | 先看 `paused_from`。若來自 decision，先 `resume` 回 decision state，再依卡片 `answer`；若來自 facts，取得事實後依上一列重開 run |
| `awaiting_user_decision` | 用 `collab report RUN_ID --format json` 取得全部 pending cards，整批呈現問題、選項、影響與建議值；取得使用者選擇後逐張 `answer`，每次都重新查狀態。不可代替使用者做風險決策 |
| `completed` / `completed_with_unverified_hard_ac` | 進入交付 |
| `escalated_for_redesign` | 回報需重設計的理由；只有使用者確認新前提後才開新 run |
| `cancelled_by_user` | 回報已取消，不再恢復 |
| `failed_preflight` | 回報缺少的 CLI／登入／brief 問題；修正環境後開新 run |
| `failed_integrity_check` | 不得 resume；提供 `collab audit RUN_ID` 結果，取得同意後才開新 run |

### 4. 交付（使用者是人類，要看得到圖）

```bash
collab report RUN_ID --format html   # → ~/.collab-orchestrator/reports/RUN_ID.html
```

1. 對話中摘要結論、卡點／風險（含使用者接受的殘留風險）與測試建議。
2. 回報 CLI 寫出的 HTML 絕對路徑；使用目前宿主的安全開檔能力開啟，或請使用者
   直接用瀏覽器開啟。現行 HTML 會從 versioned CDN 載入 Mermaid／marked，
   所以需要網路；離線時改交付 `--format md`，並明確標示圖尚未渲染。
3. `completed_with_unverified_hard_ac` 時，醒目標示未驗證的 hard AC 與
   對應測試建議。

## 鐵則

- 明確要求只授權一次預設預算 run；提高初始 ceiling 或追加預算都要再次確認。
- 決策卡（風險承擔、真僵局）永遠交使用者裁決。
- 不要聲稱 Mermaid 已渲染，除非瀏覽器／Artifact 確實成功顯示；離線 Markdown
  fallback 可以交付，但要說明限制。

## Gotchas

以下全部是真實 run（run-0faa2382）與開發過程踩過的坑：

- **中途暫停 2-3 次是正常現象，不是壞掉**。150k token 預設在「一輪順利
  收斂」邊緣，有修訂就可能觸頂暫停。這是刻意的知情 gate，不要為省來回自行
  把 ceiling 提高；依 CLI exhausted dimensions 提案，取得同意後再 extend。
- **resume 會自動沿用 execution profile**：一般直接用
  `collab resume RUN_ID`。`--fake/--real` 只是可選的一致性斷言；傳入與原 run
  不同的值會被拒絕，不能拿它切換 adapter。
- **決策卡可能同時有多張或後續再出現**：先整批呈現目前 pending cards，
  收齊選擇後逐張提交；每次 `answer` 都會繼續跑模型，提交後重新查狀態。
- **`paused_waiting_user` 不能一律只 resume**：resume 只會回到原本等待狀態，
  不會憑空補上 decision 或 facts。decision 要接著 `answer`；facts 目前需重建 brief
  並開新 run。
- **`answer`/`resume` 之後 run 是接著跑模型的**——指令會執行數分鐘，
  放背景執行，不要當成瞬間完成的操作。
- **帳面 token ≠ 全部成本**：claude 的 cache read/creation 另計
  （報告的 `+cache` 欄位），估成本要一起看。
- **`report --format html` 目前需要網路**：renderer 會從 versioned CDN 載入
  Mermaid／marked；即使 CLI help 稱為 self-contained/offline，也應以目前
  renderer 實作為準。完全離線時用 `--format md`。
- **同一 run 不要開兩個終端機同時操作**：有 run lock + CAS 防護，第二個
  操作會被拒絕（error 訊息含 concurrent modification），這是保護不是 bug。
- **brief 至少要一條 `--hard-ac`**，否則工具會自動塞一條 generic 的並
  警告——寧可自己寫清楚驗收條件。
- **hard AC 寫「無 bug」這類設計審查證明不了的條件**，run 會以
  `completed_with_unverified_hard_ac` 收尾並附測試建議——這是誠實回報，
  不是失敗。

## 參考（漸進揭露）

需要時再讀，不必一開始全載入：

- [references/cli-states.md](references/cli-states.md) — 完整指令表、
  run 狀態機與每個狀態的對應動作
- `~/claude-codex-orchestrator/README.md` — 工具能力總覽與 backlog
- `~/claude-codex-orchestrator/docs/claude-codex-collab-design-v3.1.1.md`
  — 封版設計文件（協調機制的完整規格，深度問題查這裡）
