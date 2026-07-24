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
  1.0.0
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
`--fake`；測試／示範才加。此指令是一次性、bounded 查核，沒有 `collab run` 的
watcher、dashboard、Judge 或使用者 decision card。

### 4. 解讀與交付

讀取 CLI 回報的 JSON report，逐項以白話交付：

- **confirmed**：原始 evidence 支持這個具體 claim；不等於已修好，也不等於優先級已定。
- **rejected**：現有 evidence 不支持 claim；不要把它描述成 bug。
- **unverified**：目前無法可靠確認；列出需要補哪一份 evidence。

每個 confirmed finding 都交代來源檔、行號、影響與下一步。若使用者明確要求修改，才交給
正常開發流程與真實測試；修改後可再次呼叫本 skill 驗證。若已確認事實但有多種合理修法，
提議 `$collab-design`，等待使用者同意後才啟動。

## Gotchas

- `collab review` 是證據查核，不是設計收斂；它不會自行提案、revision、Judge 或改程式。
- 每個 evidence 檔必須是 UTF-8 且不超過 1 MB；單次 pass 上限為 512 KiB。只有一份
  diff-shaped evidence 可自動按 `diff --git` file section 切分，其他過大或多個過大來源要
  先由人分批。
- finding 的 `evidence_source_id` 必須由模型明確聲明並能在該來源定位；相同文字出現在
  其他檔案不會被拿來補救，這是 fail-closed 設計。
- 這是單次 CLI 呼叫，沒有 `collab run` 的 call journal／crash-resume 保證；遇到中斷，先看
  已寫出的 report，再決定是否重跑。
- 不要因為結果是 confirmed 就直接修改；「是否修、怎麼修」仍由使用者或正常開發流程決定。

## 參考（漸進揭露）

- [references/cli-contract.md](references/cli-contract.md) — evidence 選擇、CLI flags 與結果欄位。
- [scripts/capture_git_evidence.sh](scripts/capture_git_evidence.sh) — 只讀 Git evidence 擷取器。
- `~/claude-codex-orchestrator/README.md` — CLI 安裝、完整 command help 與限制。
