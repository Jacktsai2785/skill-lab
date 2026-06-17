---
name: project-redteam-review
description: 對「整個專案」做深度盤點 + 紅隊審查 + 彙整最佳設計。先全面盤點 code 與文檔、做 code↔文檔一致性與事實查證建立事實基準，再並行派出三個不同面向的紅隊 subagent 找弱點與更好的做法，最後裁決衝突、彙整成一份精簡的最佳設計報告，並可選擇套用高信心低風險的修改。TRIGGER when 使用者說「徹底盤點整個專案」「全專案 code review」「紅隊審視」「從不同面向審視 code」「彙整成最佳設計」「red team 這個專案」「whole project audit」。DO NOT TRIGGER when 使用者只要看目前 git diff / PR 的快速 review（用 /code-review）、只要重構單一大檔（用 large-file-refactor）、或只要去除文件 AI 味（用 de-slopify）。
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

比 `/code-review`（看 diff）更徹底：盤點**整個專案**的 code 與文檔，先建立可信的事實基準，再用三個獨立紅隊視角找弱點、提更好的做法，最後彙整成一份精簡的最佳設計。

四個階段循序進行，**Phase 1 的事實基準是後面所有判斷的地基**——沒有它，紅隊很容易提出「看似合理但其實不存在」的問題。

用 TodoWrite 開四個 todo（盤點 / 驗證 / 三紅隊 / 彙整）追蹤進度，讓使用者看得到推進。

---

## Phase 0 — 全面盤點

目標：建立一份專案 manifest，並判定專案型態（決定後面三個紅隊面向）。

1. 用 Glob/Grep 掃出：進入點、核心模組、設定檔、測試、以及**文檔**（README、`docs/`、ADR、重要註解、API 說明）。先讀 README 與設定檔抓全貌，再依相依關係往核心走，別逐檔通讀。
2. 判定專案型態（web app / CLI / 資料管線 / library / service…）——這決定三個紅隊面向，對照 [references/dimensions-by-project-type.md](references/dimensions-by-project-type.md)。
3. 產出一份簡短 manifest：模組清單、各自職責一句話、關鍵檔 `path:line`、文檔清單。**這是要傳給三個紅隊的共用底稿**，務必精簡、不重複。

---

## Phase 1 — 前後比對驗證（建立事實基準）

目標：把「以為的」變成「查證過的」。三條線同時做，產出一份事實基準 + 矛盾清單：

- **code↔文檔一致性**：README / docs / 註解宣稱的行為、參數、流程，逐項對回 code 實作。每一條不符都記下 `文檔出處` vs `code 實況 (path:line)`。
- **code 事實查證**：盤點階段歸納的「某函式/結構/資料流存在且如此運作」要實際翻 code 確認，避免把臆測寫進底稿污染紅隊。
- **精簡度掃描**：標出冗長、重複用詞、複製貼上的 code 與文檔段落（這類 bloat 本身就是設計問題，也是後面「最佳設計」要收斂的對象）。

輸出兩塊：①**已查證事實基準**（紅隊只能在此基礎上提問）②**矛盾與 bloat 清單**。

---

## Phase 2 — 三紅隊並行 fan-out

依 Phase 0 判定的型態，從 [references/dimensions-by-project-type.md](references/dimensions-by-project-type.md) 選三個面向，**在同一則訊息裡用三個 Agent 呼叫並行派出**（read-only 審查，不改檔）。

每個 subagent 的 prompt 用 [references/subagent-prompt.md](references/subagent-prompt.md) 的模板，必帶：
- 共用 manifest + Phase 1 的**已查證事實基準**；
- 它被指派的單一面向，明確要求扮演紅隊（找弱點、攻擊面、可以更好的設計），但**只能基於事實基準提問，每個發現附 `path:line`**；
- 固定的結構化輸出格式（嚴重度 / 位置 / 問題 / 建議改法 / 信心），方便 Phase 3 彙整。

三個面向用「對立視角」設計，刻意讓彼此盲點互補（如安全 vs 效能常有取捨），衝突留給 Phase 3 裁決。

---

## Phase 3 — 彙整成最佳設計 ＋ 可選套用

1. **合併去重**：把三份發現按位置/主題歸併，相同問題只留一條。
2. **裁決衝突**：三個面向給出對立建議時（典型：安全強化 vs 效能、抽象 vs 簡潔），明說取捨並給出傾向，不要含糊兩面討好。
3. **收斂最佳設計**：依 [references/report-template.md](references/report-template.md) 產出報告——盤點摘要、code↔文檔矛盾、三面向發現、衝突裁決、**最佳設計建議**、以及**排序行動項**（高信心低風險排前面）。
4. **可選套用**：報告完成後，問使用者是否要把**高信心、低風險**的項目直接套到工作區；得到同意才動 code，逐項套用並回報。風險高或需取捨的項目只留在報告，不自動動手。

---

## Gotchas

- **跳過 Phase 1 = 紅隊幻覺**。沒有事實基準，subagent 會基於猜測提「假問題」。事實基準是這個 skill 與普通 review 的關鍵差異，不能省。
- **三紅隊要並行**：三個 Agent 呼叫放**同一則訊息**才會並行；分開送會被串行化、慢三倍。
- **報告自己要精簡**：使用者明確要求不要廢話/重複。每個發現一條、不換句話重講同一件事；矛盾與建議用清單不用長段落。寫完用新的眼睛刪一遍。
- **subagent 回傳的是資料不是給人看的訊息**：prompt 裡要求它回結構化發現，主流程負責彙整成人類報告。
- **大專案先抽樣再深挖**：盤點不是逐檔通讀；先用 README + 目錄結構 + 進入點建骨架，紅隊再針對高風險區深挖。
- **不要在報告階段才偷偷改 code**：套用一定要先問過使用者。

---

## 參考（漸進揭露）

- [references/dimensions-by-project-type.md](references/dimensions-by-project-type.md) — 專案型態 → 三個紅隊面向的對照表。
- [references/subagent-prompt.md](references/subagent-prompt.md) — 紅隊 subagent 的 prompt 模板與結構化輸出格式。
- [references/report-template.md](references/report-template.md) — 最終最佳設計報告的 markdown 模板。
