---
name: project-redteam-review
description: 對「整個專案」做深度盤點 + 紅隊審查 + 彙整最佳設計。先全面盤點 code 與文檔、做 code↔文檔一致性與事實查證建立事實基準、捕捉專案初衷，再並行派出三個不同視角的紅隊 subagent（不分工、同 scope）**同時審視技術健康與產品體驗**（workflow、UI/UX、貼近使用者初衷、human-friendly），各提批判與更好的設計，最後裁決衝突、彙整成報告，並**產出單一自包含的 HTML GUI**（雙欄 before/after、技術/體驗分類標籤、嚴重度色標、可折疊）自動開啟，再給使用者一個 redo 關卡決定是否重跑/換視角/深挖/套用。TRIGGER when 使用者說「徹底盤點整個專案」「全專案 code review」「紅隊審視」「從不同面向審視 code」「檢視 workflow / UI/UX 可優化處」「是否貼近使用者初衷」「彙整成最佳設計」「red team 這個專案」「whole project audit」。DO NOT TRIGGER when 使用者只要看目前 git diff / PR 的快速 review（用 /code-review）、只要重構單一大檔（用 large-file-refactor）、或只要去除文件 AI 味（用 de-slopify）。
when_to_use: 想對一個專案做超越 diff 層級的深度體檢——盤點全部 code 與文檔、確認文檔與實作相符、用多個獨立視角找出可以做得更好的地方，並收斂成一份可執行的最佳設計。適合接手陌生專案、重大重構前、或階段性品質盤點。
version: 1.0.0
tags: [quality, review, audit, red-team, architecture]
languages: all
user_invocable: true
allowed-tools:
  - Agent
  - Read
  - Glob
  - Grep
  - Bash
  - Write
  - Edit
  - TodoWrite
---

# project-redteam-review

比 `/code-review`（看 diff）更徹底：盤點**整個專案**的 code 與文檔，先建立可信的事實基準與專案初衷，再用三個獨立紅隊視角同時審視**技術健康**與**產品體驗**（workflow、UI/UX、貼近初衷、human-friendly），找弱點、提更好的做法，最後彙整成一份精簡的最佳設計。

四個階段循序進行，**Phase 1 的事實基準是後面所有判斷的地基**——沒有它，紅隊很容易提出「看似合理但其實不存在」的問題。

用 TodoWrite 開四個 todo（盤點 / 驗證 / 三紅隊 / 彙整）追蹤進度，讓使用者看得到推進。

---

## Phase 0 — 全面盤點

目標：建立一份專案 manifest，判定型態，並**捕捉專案初衷**（後面評「貼近使用者初衷」的量尺）。

1. 用 Glob/Grep 掃出：進入點、核心模組、設定檔、測試、以及**文檔**（README、`docs/`、ADR、重要註解、API 說明）。先讀 README 與設定檔抓全貌，再依相依關係往核心走，別逐檔通讀。
2. 判定專案型態（web app / CLI / 資料管線 / library / service…）——這決定**共用檢視清單（rubric）**，對照 [references/dimensions-by-project-type.md](references/dimensions-by-project-type.md)。
3. **捕捉專案初衷**：從 README / CLAUDE.md / 產品文檔歸納出「這專案要解決什麼問題、目標使用者是誰、核心使用流程長怎樣」。這是三隊評估「貼近初衷 / human-friendly」的對照基準，沒有它「產品體驗」批判會變成審查員的個人喜好。
4. 產出一份簡短 manifest：模組清單、各自職責一句話、關鍵檔 `path:line`、文檔清單、**專案初衷摘要**。**這是要傳給三個紅隊的共用底稿**，務必精簡、不重複。

---

## Phase 1 — 前後比對驗證（建立事實基準）

目標：把「以為的」變成「查證過的」。三條線同時做，產出一份事實基準 + 矛盾清單：

- **code↔文檔一致性**：README / docs / 註解宣稱的行為、參數、流程，逐項對回 code 實作。每一條不符都記下 `文檔出處` vs `code 實況 (path:line)`。
- **code 事實查證**：盤點階段歸納的「某函式/結構/資料流存在且如此運作」要實際翻 code 確認，避免把臆測寫進底稿污染紅隊。
- **精簡度掃描**：標出冗長、重複用詞、複製貼上的 code 與文檔段落（這類 bloat 本身就是設計問題，也是後面「最佳設計」要收斂的對象）。

輸出兩塊：①**已查證事實基準**（紅隊只能在此基礎上提問）②**矛盾與 bloat 清單**。

---

## Phase 2 — 三紅隊並行 fan-out（不分工，同 scope 不同視角）

**三隊不分工**：三隊看**同一份完整 scope**——技術健康 ＋ 產品體驗（workflow、UI/UX、貼近初衷、human-friendly）——各自提批判點與建議。diversity 來自**不同視角（persona）**，不是各管一塊。

依 Phase 0 型態載入共用檢視清單，再**在同一則訊息裡用三個 Agent 呼叫並行派出**（read-only，不改檔）。每個 subagent 的 prompt 用 [references/subagent-prompt.md](references/subagent-prompt.md) 模板，必帶：
- 共用 manifest（含**專案初衷**）+ Phase 1 的**已查證事實基準** + 該型態的共用 rubric；
- 一個不同的 **persona 視角**（新手使用者 / 重度使用者+維護者 / 對抗者，見 references），但明確說：**scope 相同且完整，視角只調整切入重心，技術與產品兩類都要評**；
- 只能基於事實基準與初衷提問，每個發現附 `path:line`（或文檔/流程位置）、標 `category`（技術健康 / 產品體驗）；
- 固定結構化輸出（category / 嚴重度 / 位置 / 問題 / 建議改法 / 信心），方便 Phase 3 彙整。

三隊獨立作業。三隊都點到同一問題 ＝ 高信心；只有一隊點到 ＝ 觀點差異，留給 Phase 3 裁決。

---

## Phase 3 — 彙整成最佳設計 ＋ 產出 GUI 報告

1. **合併去重**：把三隊發現按位置/主題歸併，相同問題只留一條，但記住「幾隊點到」當信心訊號（三隊都點到＝高信心）。技術健康與產品體驗的發現都要納入。
2. **裁決衝突**：三隊給出對立建議時（典型：安全 vs 效能、抽象 vs 簡潔、功能完整 vs 簡潔體驗），明說取捨並給出傾向，不要含糊兩面討好。
3. **寫結構化 JSON**：把彙整結果寫成 `<專案>/REDTEAM-REVIEW.json`，欄位見 [references/report-template.md](references/report-template.md) 的 JSON schema。**每個 before/after 的 before 必須是現況真實 code，after 是建議寫法**。把 manifest + 已查證事實基準塞進 `_context` 欄位（給 redo 重用，不渲染）。
4. **產 GUI＋Markdown**：跑 `python3 scripts/render_html.py <專案>/REDTEAM-REVIEW.json --open` 產出同名 `.html`（單一自包含、離線可開的雙欄 before/after GUI）並用系統預設瀏覽器開啟；同時依同一份 JSON 寫一份 `REDTEAM-REVIEW.md` 給純文字場景。**這是每次跑完的固定產出，不要省略 HTML。**

完成後進 Phase 4 的 redo 關卡，**不要在這裡自動套用 code**。

---

## Phase 4 — Redo 決策關卡

把報告交付後，主動列出 redo 選項讓使用者決定下一步（HTML 報告末尾也有同一份說明）。不要替使用者選；等指示再動。

- **重新全跑**：code 有大改、或想完全重來 → 從 Phase 0 重跑。
- **換/加紅隊面向重跑**：重用 `_context` 的事實基準（跳過 Phase 0–1），只用新面向重派 Phase 2。例：「改用 效能/可靠性/UX 三面向」。
- **深挖某發現**：對特定條目再派 agent 反駁或給更細修法，更新 JSON 後重渲染 HTML。
- **套用後閉環**：經同意把標「可自動套用」的高信心低風險項套到工作區 → 逐項套用、回報 diff → 對**改完的 code** 再跑一輪確認沒引入新問題。套用後重渲染時把 JSON 的 `meta.applied` 設 `true`（HTML 橫幅會變成「已套用」）。
- **結束**：留著報告，不動 code。

風險高或需取捨的項目永遠不自動套用，只留在報告。任何套用前一定先得到明確同意。

---

## Gotchas

- **跳過 Phase 1 = 紅隊幻覺**。沒有事實基準，subagent 會基於猜測提「假問題」。事實基準是這個 skill 與普通 review 的關鍵差異，不能省。
- **三紅隊要並行**：三個 Agent 呼叫放**同一則訊息**才會並行；分開送會被串行化、慢三倍。
- **三隊不分工、scope 相同**：三隊都要同時看技術健康＋產品體驗，差別只在 persona 視角。別退回「一隊只管安全、一隊只管 UX」的分工——那會漏掉跨領域問題，也不是使用者要的。
- **產品體驗要對照初衷，不是個人喜好**：「貼近使用者初衷 / human-friendly」的批判要扣回 Phase 0 捕捉的專案目的與目標使用者；否則會變成審查員自己想要的產品。
- **報告自己要精簡**：使用者明確要求不要廢話/重複。每個發現一條、不換句話重講同一件事；矛盾與建議用清單不用長段落。寫完用新的眼睛刪一遍。
- **subagent 回傳的是資料不是給人看的訊息**：prompt 裡要求它回結構化發現，主流程負責彙整成人類報告。
- **大專案先抽樣再深挖**：盤點不是逐檔通讀；先用 README + 目錄結構 + 進入點建骨架，紅隊再針對高風險區深挖。
- **不要在報告階段才偷偷改 code**：套用一定要先問過使用者（Phase 4 才可能套用）。
- **HTML 是固定產出，不是加分項**：每次跑完都要產 `.html` 並開啟；GUI 比 .md 好讀，是使用者明確要的。
- **before 必須是真實現況 code**：HTML 的價值在「可信的前後對照」。before 用臆造的 code 會讓整份報告失去意義；照抄檔案實際內容。
- **render_html.py 不需 context**：它吃 JSON 直接渲染，跑就好，別把 HTML 模板讀進 context 浪費 token。

---

## 參考（漸進揭露）

- [references/dimensions-by-project-type.md](references/dimensions-by-project-type.md) — 專案型態 → 三個紅隊面向的對照表。
- [references/subagent-prompt.md](references/subagent-prompt.md) — 紅隊 subagent 的 prompt 模板與結構化輸出格式。
- [references/report-template.md](references/report-template.md) — 報告的結構化 JSON schema、markdown 模板。
- [scripts/render_html.py](scripts/render_html.py) — 把 JSON 渲染成單一自包含 HTML（`--open` 跨平台開瀏覽器）。執行即可，不必讀內容。
