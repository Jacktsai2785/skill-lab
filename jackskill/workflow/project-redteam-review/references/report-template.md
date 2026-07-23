# 報告模板

Phase 3 先寫**結構化 JSON**（`<專案>/REDTEAM-REVIEW.json`），再用 bundled `scripts/render_html.py` 渲染成唯一一份 HTML GUI。JSON 是可被 HTML 還原的中間資料，不另寫 markdown。

## 結構化 JSON schema（HTML 的資料來源）

`render_html.py` 吃這份 JSON。未知欄位忽略、缺欄位走預設，所以可漸進填。

```json
{
  "meta": {
    "project": "專案名", "date": "YYYY-MM-DD",
    "type": "專案型態", "dimensions": ["安全", "正確性", "架構"],
    "applied": false
  },
  "teams": [
    {"idx": "①", "title": "新手 / 終端使用者", "angle": "這個視角的切入重心…",
     "counts": {"高": 2, "中": 3, "低": 1}}
  ],
  "cross_check": "多隊獨立都抓到同一問題的一致性訊號（沒有就留空字串）",
  "findings": [
    {"team": "新手 / 終端使用者", "category": "產品體驗", "severity": "高",
     "location": "path:line 或 文檔/流程位置", "problem": "一句話", "suggestion": "建議改法",
     "confidence": "高", "evidence": "直接證據、重現、測試或 code↔文檔交叉證據"}
  ],
  "conflicts": [
    {"issue": "A 主張 vs B 主張", "lean": "傾向哪個＋一句理由"}
  ],
  "before_after": [
    {"id": "A", "title": "改什麼", "severity": "高", "file": "path",
     "open": true,
     "before": "現況真實 code（照抄，含換行）",
     "after": "建議寫法"}
  ],
  "actions": [
    {"n": 1, "action": "行動", "confidence": "高", "risk": "低",
     "auto": true, "note": "auto=false 時填不能自動套用的原因"}
  ],
  "_context": {
    "manifest": "Phase 0 manifest（重跑時可重用，不渲染）",
    "fact_base": "Phase 1 已查證事實基準（重跑時可重用，不渲染）"
  }
}
```

關鍵：`teams` 是三個**視角（persona）**而非分工面向（新手使用者 / 重度使用者+維護者 / 對抗者）。`findings[].team` 要對得上某個 `teams[].title` 才會歸到該視角底下；`findings[].category` 填 `技術健康` 或 `產品體驗`（HTML 會以小標籤顯示）。`before` **必須是檔案實際內容**，不可臆造。

## 渲染與開啟（唯一產出）

```bash
python3 <skill-dir>/scripts/render_html.py <專案>/REDTEAM-REVIEW.json --consume
```

一步完成：渲染同名 `.html`（單一自包含 GUI）→ 把來源 JSON 內嵌進 HTML 後刪掉（`--consume`）→ 自動用系統預設瀏覽器開啟（要關才加 `--no-open`）。
**最後專案裡只留 `REDTEAM-REVIEW.html`**：不另寫 `.md`、不留 `.json`。資料已嵌在 HTML 的 `<script id="redteam-source">`，重跑可從那撈回 `_context`。

需要重跑或更新 applied 狀態時，先還原 JSON：

```bash
python3 <skill-dir>/scripts/render_html.py \
  <專案>/REDTEAM-REVIEW.html \
  --export-json <專案>/REDTEAM-REVIEW.json
```

## 套用關卡
HTML 交付後問使用者：要套用「排序行動項」中標 ✅（高信心低風險）的哪幾條？同意才動 code，逐項套用並回報 diff 摘要。標 ❌ 的不自動動手。套用後從 HTML 匯出 JSON，核對 before/after 確實對應實際變更，再用 `--applied --consume` 重渲染。
