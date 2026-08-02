---
name: collab-design
description: >-
  使用本機 collab-orchestrator 讓 Claude 與 Codex 進行雙盲提案、匿名交叉
  評審、issue-driven 收斂與使用者決策。TRIGGER when 使用者明確說「雙腦」
  「雙盲評審」「讓 Codex／Claude 也看一下」「collab design」「雙模型評審」或
  指定 collab-design。DO NOT TRIGGER for 一般 diff review、單純畫圖、
  bug 修復、小幅重構或既有 collab design 的一般追問。
when_to_use: >-
  用於使用者已同意啟動的重大開放式設計協作；在真僵局時呈現 evidence-backed
  decision card，但絕不代替使用者作風險或產品偏好決策。
version: >-
  4.4.0
tags:
  - workflow
  - collaboration
  - claude
  - codex
---

# collab-design — 雙腦開放式設計協調

把設計題目交給本機的 `collab` CLI（claude-codex-orchestrator）。Risk tier 決定
最低安全路徑；本 skill 代表使用者明確要求雙腦，因此另外要求 Council collaboration，
讓 Claude 與 Codex 雙盲提案、互審收斂。

## 啟動與授權

1. 使用者明確要求雙腦／雙盲／`collab design` 時，該要求視為授權啟動一次
   **預設觀測模式**的真實 run。啟動前簡短告知：通常約 5–15 分鐘，模型成本會因
   CLI 訂閱／計價與實際收斂輪數而異；過往單次約 US$1–3，只能當參考。
2. 僅由重大設計情境推測可能需要時，先提議，取得同意才啟動。
3. 測試或示範使用 `--fake`，不呼叫模型。
4. 不要在 CLI 訂閱模式預先加 `--max-tokens` 或 `--max-active-seconds`；它們會
   將觀測值改成硬暫停。需要固定 API／時間上限時才加，並先取得使用者明確同意。

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

不要把「使用者想要雙腦」假標成 High risk。保留真實 `--risk-profile`，並固定加入：

```bash
--collaboration-mode council \
--collaboration-reason "user explicitly requested independent dual-model proposals"
```

CLI 會以 risk floor 與 collaboration request 中較重的路徑執行。

### 3. 背景執行並盯進度

```bash
collab design -p "..." --hard-ac "..." \
  --collaboration-mode council \
  --collaboration-reason "user explicitly requested independent dual-model proposals" ...
collab status RUN_ID                       # 取得 run ID 後查狀態
```

保留長程序的 session／cell ID，擷取 CLI 第一段輸出的 `run RUN_ID started`。
每 30–60 秒查一次或等待新輸出，期間向使用者提供簡短進度；不要 tight polling，
也不要對同一 run 同時發出兩個 mutation 指令。

**拿到 RUN_ID 後，預設立刻啟動即時討論記錄**（除非使用者明確說不需要，或
宿主環境沒有可用的瀏覽器開啟能力）：

```bash
SKILL_DIR=~/.claude/skills/collab-design   # 或本 skill 的實際路徑
OUT=~/.collab-orchestrator/reports/RUN_ID-live.html   # 固定位置，不要用 /tmp 或 scratchpad
TOPIC="XXX 專案：YYY 卡點修正"                   # 選填，一句話講清楚這個 run 在檢視什麼
"$SKILL_DIR/scripts/watch_transcript.sh" RUN_ID "$OUT" "$TOPIC" &   # 背景執行
```

輸出固定放 `~/.collab-orchestrator/reports/`（跟 `collab report --format html`
的最終報告同一個目錄，用 `-live` 後綴跟 `RUN_ID.html` 區分，不會互相覆蓋）。
不要用 `/tmp` 或任何 session 專屬的 scratchpad 路徑——那些通常在 session
結束後就被清掉，使用者過幾天想回頭看某次 run 的討論過程會找不到檔案。

`TOPIC` 省略時會自動退回顯示 brief prompt 的前 100 字，但那通常太長、不夠像
標題——**啟動時就手動給一句話**（例如「skill-lab 全域 git hook 審查成本
開放式設計」「twstock Phase 1 FinMind token 架構修正」），讓使用者一打開
分頁就知道這個 run 在討論什麼。

`watch_transcript.sh` 會先產生一次 HTML 並嘗試自動開啟瀏覽器（`open_browser.sh`
偵測 WSL／macOS／Linux 桌面環境；宿主沒有可用的開啟方式時只會印出檔案路徑，
不算失敗，回報路徑請使用者自己開），接著每 ~15 秒重新整理內容，直到 run 進入
終態才自行結束；`awaiting_user_decision` 與可恢復的 `paused_*` 狀態會持續等待並維持
dashboard（頁面本身每 12 秒 meta-refresh，所以留著分頁不用手動
重新整理就能看到新的提案／審查／整合內容）。頁面頂部有一排任務 chip（例如
「Claude 提案」「Codex 提案」「Claude 交叉審查」），點了會捲到對應卡片；
每張卡片預設收合（`<details>`），只顯示 model／角色／狀態／時間，一眼就能
看出跑到哪一步，點開才展開完整內容——不用整頁滾動找。這個 watcher 只是把
ledger 內容渲染出來，不會對 run 下任何 mutation 指令，跟 `collab status`
輪詢可以並存。

**使用者決策是例外的互動交接，不是普通狀態文字。** 當 run 進入
`awaiting_user_decision`，watcher 必須在 live HTML 最上方以固定醒目面板列出
每張 pending card 與其選項，接著確保 `collab ui --port 8787` dashboard 正在執行
並開啟 `http://127.0.0.1:8787/?run=RUN_ID`，因此只會顯示這一次協作；需要時可由
頁面上的「查看全部歷史 run」切回總覽。live HTML 仍唯讀；只有 dashboard 的按鈕（或
明確的 `collab answer`）可提交使用者親自選定的答案。watcher 在等待期間保持
運作以維持 dashboard，絕不自動選擇。

每次 `extend-budget`／`resume` 後，仍在運作的 watcher 會自動接續更新同一份
live HTML；只有 watcher 已碰到 30 分鐘上限、程序崩潰，或你手動停止時，才需要
用同一組 RUN_ID／OUT／TOPIC 重新背景啟動。

依結束狀態處理：

| 狀態 | 動作 |
|------|------|
| `awaiting_user_facts` | 詢問缺少事實；目前 CLI 沒有補寫既有 brief 的命令，取得新事實與重開同意後 cancel 舊 run，使用完整 brief 開新 run |
| `paused_budget_exhausted` | 讀取 CLI 顯示的 exhausted dimensions，提出最小追加量、目前 tokens（含 `+cache`）與影響；**等使用者同意**後才 `extend-budget`，再 `resume` |
| `paused_agent_unavailable` | 直接 `collab resume RUN_ID` 重試一次；再失敗才回報使用者 |
| `paused_waiting_user` | 先看 `paused_from`。若來自 decision，先 `resume` 回 decision state，再依卡片 `answer`；若來自 facts，取得事實後依 `awaiting_user_facts` 列重開 run |
| `awaiting_user_decision` | 確認 live 頁首已列出全部 pending cards，並開啟 dashboard 讓使用者作答；若無法開瀏覽器，整批呈現問題、選項、影響與建議值。取得使用者選擇後逐張 `answer`，每次都重新查狀態。不可代替使用者做風險決策 |
| `completed` / `completed_with_unverified_hard_ac` | 進入交付 |
| `escalated_for_redesign` | Dashboard 顯示「用這些必修問題開新一輪」；使用者親自點擊即視為確認，以舊 run 的證據與未解條件建立並開始 successor run。不可自行點擊或在 CLI 暗自開新 run |
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
- 即時討論記錄只是唯讀渲染，`watch_transcript.sh` 本身不得對 run 下任何
  mutation 指令；`extend-budget`／`resume`／`answer` 一律照上面狀態表走，
  不能因為想讓 watcher 繼續看而自行加碼或恢復。

## Gotchas

以下全部是真實 run（run-0faa2382）與開發過程踩過的坑：

- **CLI token 是觀測值，不是預設知情 gate**。新 run 不傳 `--max-tokens` /
  `--max-active-seconds` 時，會持續收斂並記錄用量；只有呼叫者明確傳入這些
  ceiling 才會因 budget 暫停。真正的停止條件是 provider 不可用、模型輸出無效、
  真僵局或使用者決策。
- **Risk 與 Collaboration 不可混用**：本 skill 要 Council 是因為使用者要求獨立雙方案，
  不代表任務風險是 High。永遠保留真實 risk profile，讓 CLI 另外計算安全下限。
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
- **`source` 這類自由字串欄位，模型會用任意自然形式引用 id**（逗號列表、
  包在一句話裡），2026-07-24 一次真實 twstock run 連續踩過兩種形狀，都讓
  `engine.py` 的 `decision_log` 驗證誤判成「來源缺失」而卡死重試——已修好
  （改成在自由文字裡搜尋已知 id 當子字串，而不是要求整段字串完全相等），
  但這類「schema 允許的形狀 vs 驗證邏輯假設的形狀對不上」的地雷，其他自由
  字串欄位理論上也可能存在，遇到反覆 `paused_agent_unavailable` 卻查無
  網路/CLI 問題時，先懷疑這類驗證邏輯，不要一路狂重試。
- **`paused_agent_unavailable` 不保證是真的無法連線**：查
  `~/.collab-orchestrator/ledger.db` 的 `audit_events` 表（`event_type =
  'model_output_rejected'`）看 `reason` 欄位，往往是輸出被驗證邏輯拒絕，
  不是 agent 真的打不通；盲目重試在結構性 bug 情境下沒有意義。
- **即時討論記錄（`scripts/watch_transcript.sh`）預設會做，但只是唯讀
  渲染**：即使頁面看起來卡住不動，也不代表 run 掛了——先查
  `collab status RUN_ID`，watcher 只是反映 ledger 現況，它自己不會、也
  不該去 resume 或 extend 任何東西。watcher 在可恢復暫停時會保持運作，
  因此使用者 resume 後同一頁會自動接續更新；只有終態、30 分鐘上限、崩潰或
  手動停止後，才需要重新啟動 watcher。
- **`awaiting_user_decision` 不能只在頁首顯示狀態字串**：live transcript
  必須渲染卡片、開啟 dashboard 並持續 watcher，否則使用者看見一串「已接受」
  卻不知道輪到自己。dashboard 的按鈕仍然只在使用者點擊後才會呼叫 `answer`。
- **從即時討論記錄進入 dashboard 必須帶 `?run=RUN_ID`**：根網址是歷史總覽，
  會顯示同一台機器上的其他 run；若不帶篩選，使用者很容易把舊 run 當成目前這輪。
- **選「重新設計」會結束整個舊 run**：不需要逐張回答其餘決策卡。Dashboard 的
  successor 按鈕會把所有未解 issue、原始 evidence quote 與 resolution condition 帶入新
  brief，並額外轉為 hard acceptance criteria；只有使用者親自按下才會開始新 run。

## 參考（漸進揭露）

需要時再讀，不必一開始全載入：

- [references/cli-states.md](references/cli-states.md) — 完整指令表、
  run 狀態機與每個狀態的對應動作
- [scripts/watch_transcript.sh](scripts/watch_transcript.sh) /
  [scripts/collab_transcript.py](scripts/collab_transcript.py) /
  [scripts/open_browser.sh](scripts/open_browser.sh) — 即時討論記錄的產生器
  與跨平台開瀏覽器 helper；watcher 純讀 ledger/artifacts，但在需要使用者
  決策時會啟動／開啟 dashboard 作為使用者親自提交答案的入口，不碰 run 的任何狀態
- `~/claude-codex-orchestrator/README.md` — 工具能力總覽與 backlog
- `~/claude-codex-orchestrator/docs/claude-codex-collab-design-v3.1.1.md`
  — 封版設計文件（協調機制的完整規格，深度問題查這裡）
