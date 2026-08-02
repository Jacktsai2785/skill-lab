---
name: collab-review
description: >-
  用本機 collab CLI 的 review 指令，讓 Claude 與 Codex 對同一份明確 evidence
  進行獨立、來源可驗證的工程查核。TRIGGER when 使用者明確說「collab review」、
  「雙腦查證」「雙模型 code review」「查證這個 workflow／log／大型改動」或指定
  collab-review。DO NOT TRIGGER for 開放式設計取捨、一般小型 diff、直接 bug 修復，
  或尚未提供／授權可檢查材料的猜測性問題。
when_to_use: >-
  用於確認既有程式、diff、workflow、log 或測試輸出是否支持一項工程 finding；輸出
  confirmed、rejected 或 unverified 的來源引文結果，不提出設計方案也不修改程式。
version: >-
  1.1.0
tags:
  - workflow
  - review
  - evidence
  - claude
  - codex
---

# collab-review — 雙腦證據查核

把已授權的程式碼、diff、workflow、log 與測試輸出交給本機 `collab review`。Claude
與 Codex 會各自檢查同一批 evidence；每個輸出 finding 都必須能定位到一個具名來源。

## 執行步驟

### 1. 確認這是查證題

適用問題是「這段程式是否真的有 race condition？」「這個 workflow 的 timeout 是否
真的會累積？」「log 是否支持這個根因？」。若問題其實是「有多種修法，該選哪一種」，
先完成查證，再提議使用 `$collab-design`；不要在本 skill 中自行開 `collab run`。

### 2. 準備受控 evidence

只讀取使用者已提供或已明確授權檢視的材料。依問題選擇最小充分集合：

- 程式變更：diff、相關實作檔、相關測試。
- workflow 卡點：Mermaid／流程文件、實作程式、log、測試或重現輸出。
- 大型 code review：明確指定的檔案集合與檢查目標；不可把整個 repo 無差別塞入。

需要擷取目前 Git 狀態時，可用 `scripts/capture_git_evidence.sh OUTPUT_DIR [BASE_REF]`
產生 working tree、staged、commit-range diff 與 status；它只讀 Git，且拒絕覆寫既有
輸出目錄。其餘材料直接使用原始檔案，不要重述成摘要。

### 3. 前置檢查並呼叫 CLI

```bash
command -v collab || "$HOME/claude-codex-orchestrator/.venv/bin/collab" --help
collab review \
  --evidence /absolute/path/implementation.py \
  --evidence /absolute/path/workflow.mmd \
  --evidence /absolute/path/failure.log \
  --prompt "查證 timeout 是否會因逐 ref 呼叫而累積" \
  --hard-ac "每個 finding 必須有可定位的原文來源"
```

用使用者的語言寫 `--prompt`，用 `--hard-ac` 限定可驗證的完成條件。真實 run 不加
`--fake`；測試／示範才加。

`collab review` 現在跟 `collab run` 走同一個 Engine：指令會印出 `run <run_id>
started`，在背景推進到收斂或卡住為止才回傳（單次呼叫仍會等到底，但過程走
checkpoint/journal，可中斷恢復，不是不可觀測的黑箱）。分歧的 finding 由 AI 自己走
Rebuttal → Judge-lite 裁到底，只有雙方 judge 真的分不出優劣（no-dominance）才會停在
`awaiting_user_decision` 等你決定；指令結束時若停在那裡，CLI 會印出待答的 `card_id`
與兩個選項 (`confirmed`/`rejected`)。

### 4. 若停在 no-dominance，回答後才算完成

```bash
collab answer <run_id> <card_id> --choice confirmed   # 或 rejected
```

其餘場景可用既有的 run 管理指令查詢／恢復同一個 run（不需要另開一套指令）：

```bash
collab status <run_id> --data-dir ~/.collab-orchestrator
collab report <run_id> --format json --data-dir ~/.collab-orchestrator
collab continue-run <run_id>   # 進程中斷後、在背景worker/dashboard重啟時繼續推進
collab resume <run_id>         # 從 paused_* 狀態恢復（例如模型逾時）
collab calls <run_id>          # 逐筆檢視每次模型呼叫的 journal 狀態
collab ui                      # dashboard 能看到 review run 的進度與待答卡片
```

`collab report <run_id>` 對 review run 只支援 `--format json`（md/html 是
`collab design` 報告的格式）；review 的報告一律是這份三態 JSON。

### 5. 解讀與交付

讀取 CLI 回報（或 `collab report --format json`）的 JSON report，逐項以白話交付：

- **confirmed**：原始 evidence 支持這個具體 claim；不等於已修好，也不等於優先級已定。
  可能是 AI 自己驗證出來，也可能是 no-dominance 後你選的。
- **rejected**：現有 evidence 不支持 claim；不要把它描述成 bug。同樣可能來自 AI 自行
  裁決，或你在 no-dominance 卡片上的選擇。
- **unverified**：保留給「查無 evidence 佐證」的情況（例如模型工具故障、報不出可定位
  的引文）——這不是「AI 吵不出結果」，那種情況會走 no-dominance 卡片，不會標
  unverified。

每個 finding 除了三態結果，report 裡多了一個 `convergence` 欄位，記錄它是否被
verifier 質疑過、rebuttal 站不站得住、judge-lite 兩個判官的裁決理由，或使用者卡片的
選擇——交付時可以引用這段說明「為什麼」，不只是給結論。頂層還有 `convergence_summary`
統計整批 finding 各自走到哪一步。

每個 confirmed finding 都交代來源檔、行號、影響與下一步。若使用者明確要求修改，才交給
正常開發流程與真實測試；修改後可再次呼叫本 skill 驗證。若已確認事實但有多種合理修法，
提議 `$collab-design`，等待使用者同意後才啟動。

## Gotchas

- `collab review` 是證據查核，不是設計收斂；它不會自行提案、開放式 revision，也不會
  改程式——這點沒變。變的是「分歧怎麼收斂」：現在有 Rebuttal → Judge-lite 兩個模型
  自己裁到底，design 既有的 no-dominance 判準原班重用，只是判斷式改成二元
  confirmed/rejected，不是 design 那種開放式方案優劣。
- 每個 evidence 檔必須是 UTF-8 且不超過 1 MB；單次 pass 上限為 512 KiB。只有一份
  diff-shaped evidence 可自動按 `diff --git` file section 切分，其他過大或多個過大來源要
  先由人分批。
- finding 的 `evidence_source_id` 必須由模型明確聲明並能在該來源定位；相同文字出現在
  其他檔案不會被拿來補救，這是 fail-closed 設計。
- 現在有 run_id、checkpoint/journal 與 crash-resume：中斷後用 `collab status`/`collab
  calls` 檢查進度，`collab continue-run`／`collab resume` 接著跑，不需要整個重跑。
- 不要因為結果是 confirmed 就直接修改；「是否修、怎麼修」仍由使用者或正常開發流程決定。
- 停在 `awaiting_user_decision` 不代表查核失敗——那是 AI 真的分不出優劣，才刻意保留給你
  拍板；answer 完才會落地成三態之一並產出最終 report。

## 參考（漸進揭露）

- [references/cli-contract.md](references/cli-contract.md) — evidence 選擇、CLI flags 與結果欄位。
- [scripts/capture_git_evidence.sh](scripts/capture_git_evidence.sh) — 只讀 Git evidence 擷取器。
- `~/claude-codex-orchestrator/README.md` — CLI 安裝、完整 command help 與限制。
