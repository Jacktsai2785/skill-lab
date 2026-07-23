---
name: project-redteam-review
description: >-
  對整個專案執行深度盤點、code↔文檔查證、三視角紅隊審查、衝突裁決與可套用的
  HTML 報告。僅在使用者明確要求「徹底盤點整個專案」「全專案 code review」
  「紅隊審視」「whole project audit」，或明確指定 project-redteam-review 時使用。
  適合接手陌生專案、重大重構前及階段性品質盤點。不要用於只看 git diff／PR、
  單檔重構、一般問答或單純去除文件 AI 味。
---

# project-redteam-review

比 `/code-review`（看 diff）更徹底：盤點**整個專案**的 code 與文檔，先建立可信的事實基準與專案初衷，再用三個獨立紅隊視角同時審視**技術健康**與**產品體驗**（workflow、UI/UX、貼近初衷、human-friendly），找弱點、提更好的做法，最後彙整成一份精簡的最佳設計。

五個階段循序進行，**Phase 1 的事實基準是後面所有判斷的地基**——沒有它，紅隊很容易提出「看似合理但其實不存在」的問題。

用目前宿主提供的計畫／任務追蹤能力記錄五個步驟（盤點 / 驗證 / 三紅隊 / 彙整 / 套用關卡），讓使用者看得到推進。

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

依 Phase 0 型態載入共用檢視清單，再用目前宿主的並行協作能力一次派出三個 subagent（read-only，不改檔）；Claude Code 可在同一則訊息發出三個 Agent 呼叫，其他宿主使用其等價的 concurrent delegation。每個 subagent 的 prompt 用 [references/subagent-prompt.md](references/subagent-prompt.md) 模板，必帶：
- 共用 manifest（含**專案初衷**）+ Phase 1 的**已查證事實基準** + 該型態的共用 rubric；
- 一個不同的 **persona 視角**（新手使用者 / 重度使用者+維護者 / 對抗者，見 references），但明確說：**scope 相同且完整，視角只調整切入重心，技術與產品兩類都要評**；
- 以事實基準與初衷為共同起點，每個發現附 `path:line`（或文檔/流程位置）與直接證據，並標 `category`（技術健康 / 產品體驗）；找到相反的一手證據時可提出事實基準修正；
- 固定結構化輸出（category / 嚴重度 / 位置 / 問題 / 建議改法 / 信心），方便 Phase 3 彙整。

三隊獨立作業。多隊都點到同一問題只算「一致性訊號」，不能單獨等同高信心；高信心仍須有直接 code 證據、可重現行為、測試結果或 code↔文檔交叉證據。只有一隊點到則保留為觀點差異，交由 Phase 3 裁決。

---

## Phase 3 — 彙整成最佳設計 ＋ 產出 GUI 報告

1. **合併去重**：把三隊發現按位置/主題歸併，相同問題只留一條，記錄「幾隊點到」作為一致性訊號；不要只因三隊同意就提升為高信心。技術健康與產品體驗的發現都要納入。
2. **裁決衝突**：三隊給出對立建議時（典型：安全 vs 效能、抽象 vs 簡潔、功能完整 vs 簡潔體驗），明說取捨並給出傾向，不要含糊兩面討好。
3. **寫結構化 JSON（中間檔）**：把彙整結果寫成 `<專案>/REDTEAM-REVIEW.json`，欄位見 [references/report-template.md](references/report-template.md) 的 JSON schema。**每個 before/after 的 before 必須是現況真實 code，after 是建議寫法**。manifest + 已查證事實基準塞進 `_context`。這只是渲染用的中間檔，下一步會被嵌進 HTML 後刪掉。
4. **產出唯一一份 HTML 並自動開啟**：解析本 skill 所在目錄，執行 bundled renderer。Claude Code 使用 `python3 "${CLAUDE_SKILL_DIR}/scripts/render_html.py" <專案>/REDTEAM-REVIEW.json --consume`；其他宿主使用其提供的 skill 路徑解析能力，執行本檔旁的 `scripts/render_html.py`。renderer 會渲染同名 `.html`、內嵌完整來源資料、刪除中間 JSON，並嘗試用系統預設瀏覽器開啟；不需要開啟時加 `--no-open`。**最後專案裡只留一份 `REDTEAM-REVIEW.html`，不要另寫 `.md` 或保留 `.json`。**

完成後進 Phase 4 的套用關卡，**不要在這裡自動套用 code**。

---

## Phase 4 — 套用關卡（Apply gate）

報告交付後，唯一要問的是：**這些建議要套用哪幾條？** 主動列出標「可自動套用」(✅) 的高信心低風險項，讓使用者選——全套 / 選幾條 / 都不套。**等明確指示再動 code。**

- 得到同意後逐項套用、回報 diff 摘要；風險高或需取捨的項目（❌）永遠不自動套用，只留在報告。
- 套用後先從 HTML 匯出內嵌資料：`python3 <skill-dir>/scripts/render_html.py <專案>/REDTEAM-REVIEW.html --export-json <專案>/REDTEAM-REVIEW.json`。核對並更新 before/after 使其對應實際變更，再執行 `python3 <skill-dir>/scripts/render_html.py <專案>/REDTEAM-REVIEW.json --applied --consume` 重渲染；橫幅會變成「已套用」。
- 套用完可順口問一句「要不要針對改動的部分再跑一輪確認沒改壞？」——要的話就是**再跑一次本 skill**，不是特殊模式。

> 不需要 redo 選單。想換視角重審、深挖某條、或 code 大改後重跑，使用者直接再講一句重新觸發 skill 即可。先用 renderer 的 `--export-json` 從既有 HTML 取回 `_context`；重用前抽查關鍵檔案是否已變動，不能把舊事實基準當成永遠有效。

---

## Gotchas

- **跳過 Phase 1 = 紅隊幻覺**。沒有事實基準，subagent 會基於猜測提「假問題」。事實基準是這個 skill 與普通 review 的關鍵差異，不能省。
- **事實基準可被一手證據修正**：它是共同起點，不是不可推翻的真理。紅隊若附上新的 `path:line`、測試結果或可重現步驟，可以提出 correction；主流程要先驗證再更新基準。
- **三紅隊要並行**：使用目前宿主的 concurrent delegation；在 Claude Code 中把三個 Agent 呼叫放在同一則訊息。不要不必要地串行等待。
- **三隊不分工、scope 相同**：三隊都要同時看技術健康＋產品體驗，差別只在 persona 視角。別退回「一隊只管安全、一隊只管 UX」的分工——那會漏掉跨領域問題，也不是使用者要的。
- **產品體驗要對照初衷，不是個人喜好**：「貼近使用者初衷 / human-friendly」的批判要扣回 Phase 0 捕捉的專案目的與目標使用者；否則會變成審查員自己想要的產品。
- **報告自己要精簡**：使用者明確要求不要廢話/重複。每個發現一條、不換句話重講同一件事；矛盾與建議用清單不用長段落。寫完用新的眼睛刪一遍。
- **subagent 回傳的是資料不是給人看的訊息**：prompt 裡要求它回結構化發現，主流程負責彙整成人類報告。
- **大專案先抽樣再深挖**：盤點不是逐檔通讀；先用 README + 目錄結構 + 進入點建骨架，紅隊再針對高風險區深挖。
- **不要在報告階段才偷偷改 code**：套用一定要先問過使用者（Phase 4 才可能套用）。
- **唯一產出是 HTML，且會自動開瀏覽器**：每次跑完只留一份 `.html`（資料內嵌其中），`--consume` 會刪掉中間 JSON、預設自動開啟。不要再寫 `.md`、不要在專案留 `.json`——使用者只要瀏覽器上那一份。
- **before 必須是真實現況 code**：HTML 的價值在「可信的前後對照」。before 用臆造的 code 會讓整份報告失去意義；照抄檔案實際內容。
- **render_html.py 不需 context**：它吃 JSON 直接渲染，跑就好，別把 HTML 模板讀進 context 浪費 token。

---

## 參考（漸進揭露）

- [references/dimensions-by-project-type.md](references/dimensions-by-project-type.md) — 專案型態 → 三個紅隊面向的對照表。
- [references/subagent-prompt.md](references/subagent-prompt.md) — 派出紅隊前必讀；包含 subagent prompt 模板與結構化輸出格式。
- [references/report-template.md](references/report-template.md) — 產出報告前必讀；包含結構化 JSON schema 與渲染／還原流程。
- [scripts/render_html.py](scripts/render_html.py) — 把 JSON 渲染成單一自包含 HTML，也能從 HTML 匯出內嵌 JSON。執行即可，不必讀內容。
