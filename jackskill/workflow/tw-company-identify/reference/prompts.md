# Extraction Prompts (verbatim)

兩支 prompt 來自 [taiwan-company/services/company_extractor.py](/home/jacktsai/taiwan-company/services/company_extractor.py)，已在實際營運中驗證。修改前請小心 — 規則措辭、JSON 格式範例都會影響 Claude 的輸出穩定度。

## Text extraction

```text
請從以下文字中找出所有疑似公司或機構的名稱。
規則：
1. 包含「股份有限公司」或「有限公司」的請完整列出
2. 看起來是公司或組織但沒有標準結尾的名稱也請列出
3. 不要捏造不存在於文字中的名稱
4. 只回傳 JSON 陣列，例如：["AA科技股份有限公司", "BB有限公司", "CC創新"]
5. 如果文字中沒有任何公司名稱，回傳空陣列 []
6. 不要有任何其他說明文字，只輸出 JSON 陣列

文字內容：
{text}
```

- `{text}` 替換為要分析的內容；建議截斷至 8000 字元以內。
- 預期輸出：純 JSON 陣列，元素為字串。

## Image extraction

```text
請讀取圖片，找出其中的台灣公司資料。

【輸出規則】
1. 若圖片有「統一編號」欄位，請輸出 JSON 陣列，每筆格式為 {"name": "公司名稱", "tax_id": "統一編號"}
2. 若圖片沒有統一編號，請輸出純字串陣列 ["公司名稱A", "公司名稱B"]
3. 統一編號為8位數字，請完整抓取，不要省略
4. 只抓公司或機構名稱，不要列人名、地址、電話、欄位標題
5. 只輸出 JSON，不要任何說明文字
```

- 適用情境：發票、名片、簡報截圖、財報封面。
- 預期輸出：當圖含統編 → 物件陣列；否則純字串陣列。

## Parsing 注意事項

兩支 prompt 都要求「只輸出 JSON」，但 LLM 偶爾會夾雜「以下是…」說明。腳本實作以 `raw.find("[") / raw.rfind("]")` 取出最外層 `[...]` 區塊再 `json.loads`，可容忍前後雜訊。

圖片 prompt 第 1 條期望物件含 `name` + `tax_id`，但實務上常見變體（中文鍵名、其他語意鍵），腳本對 `name`/`公司名稱`/`募資企業名稱` 與 `tax_id`/`統一編號` 都做了相容處理。

## Classification rule

抽取後依結尾字串分類，規則一致：

| 結尾條件 | 分類 |
|---------|------|
| 含「股份有限公司」 | `valid` |
| 含「有限公司」但非股份有限公司 | `excluded`（小型行號，預設略過） |
| 兩者皆無 | `uncertain`（呼叫端決定） |

實作見 [scripts/identify.py `classify()`](../scripts/identify.py)。
