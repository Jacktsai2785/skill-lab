# 報告模板

Phase 3 先寫**結構化 JSON**（`<專案>/REDTEAM-REVIEW.json`），再用 `scripts/render_html.py` 渲染成 HTML GUI，並另寫一份 markdown。三者同源。

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
  "cross_check": "多隊獨立都抓到同一問題的高信心訊號（沒有就留空字串）",
  "findings": [
    {"team": "新手 / 終端使用者", "category": "產品體驗", "severity": "高",
     "location": "path:line 或 文檔/流程位置", "problem": "一句話", "suggestion": "建議改法"}
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

## 渲染與開啟

```bash
python3 scripts/render_html.py <專案>/REDTEAM-REVIEW.json --open
```

---

## Markdown 版（純文字場景備援）

**精簡優先**：每點一條、不重複、清單勝於長段落。

```markdown
# 紅隊審查與最佳設計 — {專案名}
> 日期：{YYYY-MM-DD}　型態：{專案型態}　三面向：{①}/{②}/{③}

## 1. 盤點摘要
- 模組與職責（一行一個）：…
- 進入點 / 核心檔：`path:line`
- 文檔清單：…

## 2. code↔文檔矛盾
| 文檔出處 | 宣稱 | code 實況 (path:line) | 建議 |
|---|---|---|---|
（無則寫「未發現」）

## 3. 三面向發現
### ① {面向}
- [高] `path:line` — 問題 → 建議改法
### ② {面向}
- …
### ③ {面向}
- …

## 4. 衝突裁決
針對三面向對立的建議，明說取捨與傾向：
- 議題：{如「為輸入驗證加 schema」vs「保持輕量」} → 傾向：{選哪個＋一句理由}

## 5. 最佳設計建議
收斂後的目標設計（不是逐條問題，而是整體該長什麼樣）：
- …

## 6. 排序行動項
| # | 行動 | 信心 | 風險 | 可自動套用 |
|---|---|---|---|---|
| 1 | … | 高 | 低 | ✅ |
| 2 | … | 中 | 中 | ❌（需確認） |
（高信心低風險排前面；標 ✅ 的是「可選套用」候選）
```

## 套用環節
報告交付後問使用者：是否套用第 6 節中標 ✅ 的項目？同意才動 code，逐項套用並回報 diff 摘要。標 ❌ 的不自動動手。
