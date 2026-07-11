# Call Memo Extract Prompt

LLM prompt used by `scripts/memo.py` to extract Call Memo fields from a transcript. Verbatim from
`taiwan-company/services/memo_extractor.py:50-67` so behaviour stays identical across projects.

## Template

```
你是一位專業的投資分析師助理。以下是與「{company}」的訪談逐字稿。

請從逐字稿中提取以下欄位的資訊，以 JSON 格式回傳。
- 若某欄位在逐字稿中有提及，請整理成清楚的中文句子或條列。
- 若未提及，請回傳空字串 ""。
- 回傳純 JSON，不要加 markdown code block 或其他說明。

需提取的欄位：
{
{fields_desc}
}

逐字稿內容：
---
{transcript[:12000]}
---

請直接回傳 JSON 物件。
```

## Substitutions

| placeholder | substitution |
|-------------|--------------|
| `{company}` | `--company NAME` 參數值 |
| `{fields_desc}` | 動態組合，每行 `  "{key}": "{label}（{description}）",` |
| `{transcript[:12000]}` | 逐字稿前 12,000 字（截斷） |

## fields_desc 範例（bundled 模式）

```
  "deal_source": "案件來源（例：自行開發、某人介紹。若未提及請填「自行開發」）"
  "interviewees": "受訪人（受訪者姓名與職稱，多人以頓號分隔）"
  "paid_in_capital": "實收資本額（NT$ 金額，例：5,000萬）"
  ...（共 24 欄）
```

## fields_desc 範例（custom 模式）

自訂範本沒有英文 key 與額外描述，會用中文 label 同時當 key 與 description：

```
  "案件來源": "案件來源（案件來源）"
  "受訪人": "受訪人（受訪人）"
  ...
```

## Response 處理

LLM 回傳後的處理流程（`extract_fields` in `memo.py`）：
1. 去掉 markdown code fence (```json ... ```)
2. 用 regex `\{[\s\S]*\}` 抓出 JSON 區塊
3. `json.loads`，失敗則回空 dict
4. 確保所有 schema key 都存在（缺的填空字串）
5. 過濾掉 schema 外的多餘 key

## Truncation

逐字稿超過 12,000 字會被截斷。長訪談請呼叫端先分段或自行 chunking 後合併結果。

## Why this prompt works

- **「請整理成清楚的中文句子或條列」** — 避免 LLM 直接 quote 原文，產出可讀的整理版
- **「若未提及請回傳空字串」** — 阻止 LLM 編造資訊
- **「不要加 markdown code block」** — 簡化 parsing；regex fallback 仍能處理 LLM 不聽話的情況
