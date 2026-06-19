---
name: tw-company-identify
description: >
  Identify and normalize Taiwan companies from unstructured input (text, image, or
  partial name). Three-stage pipeline: (1) extract candidate names via Claude LLM,
  (2) classify by legal-entity suffix (股份有限公司 / 有限公司 / uncertain),
  (3) normalize via g0v + GCIS APIs to obtain official name, 統一編號, listing
  status (上市/上櫃/興櫃/創新板/非公發), capital, representative, address, directors.
  TRIGGER when: user gives raw text/image/screenshots and asks to identify
  Taiwan companies, normalize 公司名稱 to official form via 統一編號, classify a
  list of company-like strings, or says "辨識公司" / "抽取公司名" / "公司正規化" /
  "從這份文件找出公司".
  DO NOT TRIGGER when: user already has the exact 公司名/統編 and only needs the
  full registry record (use tw-company-lookup), or wants PE-style due-diligence
  summary (use customer-intel / investment-research).
tags: [taiwan, identification, llm, government-api]
version: 1
source: manual
user_invocable: true
---

# Taiwan Company Identify

把任意輸入（一段文字、圖片、或單一公司名/統編）轉成已正規化、附基本元資料的台灣公司物件。

## Pipeline

```
input ──► (1) Extract ──► (2) Classify ──► (3) Normalize ──► JSON
         Claude LLM       suffix rule       g0v / GCIS API
```

1. **Extract** — Claude LLM 從文字/圖片找出疑似公司名（含未含「股份有限公司」結尾者）；圖片若含「統一編號」欄位也會抓出統編。
2. **Classify** — 依結尾分類：
   - `valid`：含「股份有限公司」
   - `excluded`：含「有限公司」但非股份有限公司（多為小型行號，預設略過）
   - `uncertain`：兩者皆無（呼叫端決定如何處理）
3. **Normalize** — `valid` 名單透過 ronnywang g0v API（主）+ GCIS App1 OData API（fallback）查詢統編、代表人、資本額、地址、董監事；上市狀態（上市/上櫃/興櫃/創新板/非公發）由 TWSE/TPEX/GISA 公開 API 即時比對（24h cache）。

## Setup

```bash
pip install -r ~/.claude/skills/tw-company-identify/scripts/requirements.txt
# 圖片模式必要：
export ANTHROPIC_API_KEY=sk-ant-...
```

文字抽取模式若沒有 `ANTHROPIC_API_KEY`，可用 `--provider cli` fallback 到本機 `claude` CLI。
純 normalize（`--name` / `--tax-id`）不需 LLM，無 API key 即可執行。

## Usage

```bash
# 從文字抽取（最常用）
python ~/.claude/skills/tw-company-identify/scripts/identify.py --text "今天拜訪了台積電股份有限公司"

# 從 stdin 抽取（搭配 cat / pipe）
cat meeting_notes.md | python ~/.claude/skills/tw-company-identify/scripts/identify.py --stdin

# 從圖片抽取（發票、名片、簡報截圖）
python ~/.claude/skills/tw-company-identify/scripts/identify.py --image invoice.png

# 純 normalize：已知公司名查官方資料
python ~/.claude/skills/tw-company-identify/scripts/identify.py --name "台積電"

# 純 normalize：已知統編查官方資料
python ~/.claude/skills/tw-company-identify/scripts/identify.py --tax-id 22099131

# 只抽取分類，不打 GCIS（離線/省 API）
python ~/.claude/skills/tw-company-identify/scripts/identify.py --text "..." --no-enrich
```

### Options

| flag | 說明 |
|------|------|
| `--text TEXT` | 直接吃字串 |
| `--stdin` | 從 stdin 讀文字 |
| `--image PATH` | 圖片檔（jpg/png/webp/gif）|
| `--name NAME` | 跳過抽取，直接 normalize 單一公司名 |
| `--tax-id TAXID` | 跳過抽取，直接 normalize 單一統編 |
| `--no-enrich` | 只跑 extract+classify，不呼叫 GCIS |
| `--provider {anthropic,cli}` | LLM 提供者，預設 `anthropic`，無 API key 時 fallback `cli` |
| `--json-only` | 只輸出 JSON 到 stdout（預設另印 summary 到 stderr）|

## Output Schema

```json
{
  "valid": [
    {
      "name": "台灣積體電路製造股份有限公司",
      "tax_id": "22099131",
      "listing_status": "上市",
      "representative": "魏哲家",
      "capital": 259303804580,
      "authorized_capital": 280500000000,
      "address": "新竹科學園區新竹市力行六路8號",
      "par_value": 10,
      "total_shares": 25930380458,
      "directors": [
        {"name": "...", "title": "董事長", "representative_of": "", "shares": 0, "ratio": 0.0}
      ]
    }
  ],
  "excluded": [{"name": "某某有限公司"}],
  "uncertain": [{"name": "某某創新"}]
}
```

`--no-enrich` 模式下 `valid` 陣列每筆只有 `name`，無 GCIS 欄位。

## Reference

- [reference/prompts.md](reference/prompts.md) — text/image 抽取 prompts 完整版
- [reference/api-spec.md](reference/api-spec.md) — g0v/GCIS/TWSE/TPEX/GISA 端點規格

## Related Skills

- **tw-company-lookup** — 本 skill 是 tw-company-lookup 的 **API layer**：lookup 腳本呼叫本 skill 的 `identify.py` 取得 API 資料，再補上 findbiz 的工廠/歷史/所營事業/經理人。若只需基本資料請直接用本 skill，不必啟動 Playwright。
- **customer-intel** — B2B 客戶情蒐 + 銷售報告。本 skill 做完辨識，可接 customer-intel 做後續研究。
- **investment-research** — 投資面研究、財報分析。上市狀態由本 skill 提供。

## Troubleshooting

| 問題 | 解法 |
|------|------|
| g0v API 503 / timeout | 自動 fallback 到 GCIS App1（by tax_id），但 GCIS 不含董監事；若都失敗，回傳空 enrich 欄位（`tax_id=""`）|
| 上市狀態總是「非公發」 | 24h cache 可能還沒載入；首次呼叫會花約 5–10 秒下載 TWSE/TPEX/GISA 資料 |
| 圖片抽取無結果 | 確認圖片含可辨識的中文公司名；測試時可先用 `--text` 把圖片中的字貼進來檢查 |
| `tax_id` 看起來不像 8 碼數字 | 抽取階段已跳過，但若呼叫端傳了非 8 碼到 `--tax-id`，會直接回空 |
| `claude` CLI fallback 失敗 | 改設 `ANTHROPIC_API_KEY` 走 SDK；CLI 模式對長輸入較不穩定 |
| 抓到非公司名（人名、地址）| Prompt 已強調「只抓公司或機構名稱」，但偶有誤判；呼叫端可自行對 `valid`/`uncertain` 做二次過濾 |

## Notes

- **不維護 state**：每次呼叫都是 stateless；若要 dedup 跨次結果請呼叫端自理。
- **創櫃板**目前 TPEX 無公開 JSON API，無法自動辨識，會被歸為「非公發」。
- 上市狀態 cache TTL = 24 小時，重啟 process 後重新載入。
- Prompt 與 classifier 規則逐字保留自 [taiwan-company](https://github.com/) 專案的 `services/company_extractor.py`，跨專案行為一致。
