# Custom Template Inference

`memo.py --template path/to/your_format.docx` 會自動推斷欄位結構，產生對應的 LLM prompt schema 與 cell 填寫對應。

## 偵測規則

`infer_fields_from_template()`：
1. 用 `python-docx` 開啟 DOCX
2. Walk 所有 `<w:tbl>` 表格的所有 row 的所有 cell
3. 取每個 cell 的第一個 paragraph 文字
4. 若 strip 後以「：」（**全形冒號**）結尾 → 視為 label
5. label 去掉「：」後當作 JSON key（中文）
6. 重複 label 自動 dedup

## 範本須符合

- 至少有一個表格（`<w:tbl>`）
- 每個欄位是表格的一個 cell
- cell 的第一行是 label，**必須以全形「：」結尾**
- label 文字會直接做為 JSON key 與 prompt 中的欄位名稱

## 不會被偵測的欄位

- 不在表格內的段落（除了 hardcoded 的「訪談日期：」會被處理）
- 第一行不以「：」結尾的 cell（例如純數字、純標題）
- label 用半形冒號 `:` 而非全形「：」的 cell

## 範例

假設你的 `my_format.docx` 有一個 2 欄表格：

| label cell | (空白 value cell) |
|-----------|--------------------|
| `案件來源：` | （空白）|
| `受訪人：` | （空白）|
| `公司願景：` | （空白）|
| `投資建議：` | （空白）|

執行：

```bash
python ~/.claude/skills/tw-call-memo/scripts/memo.py \
  --company "台積電" --text "..." \
  --template ~/my_format.docx \
  --docx /tmp/out.docx
```

skill 會：
1. 偵測到 4 個 label：`案件來源`、`受訪人`、`公司願景`、`投資建議`
2. 產生 prompt schema：
   ```json
   {
     "案件來源": "案件來源（案件來源）",
     "受訪人": "受訪人（受訪人）",
     "公司願景": "公司願景（公司願景）",
     "投資建議": "投資建議（投資建議）"
   }
   ```
3. Claude 回傳對應 4 個中文 key 的 JSON
4. `_fill_cell` 把每個 value 接在對應 cell 的 label 後

## 限制

- **沒有 description**：bundled 範本有「（NT$ 金額，例：5,000萬）」這類提示，自訂範本只能用 label 自己描述自己
- **單字 label 表現較差**：如果 label 太籠統（例如「備註：」），Claude 不知道要填什麼
- **Header 段落不偵測**：除了 hardcoded 的「訪談日期：」會替換 `2025/X/X` placeholder，其他 header 文字（評估人、部門等）目前不處理
- **同名 label 只取第一個**：表格裡有多個「備註：」cell 只會偵測一次

## 想要描述更精確？

兩種做法：
1. **改 label 變更具體**：把「備註：」改成「風險評估備註：」，prompt 更清楚
2. **直接用 bundled 範本**：bundled 的 20 欄位都附了 example/description，效果最穩定

## Debug

```bash
# 看 skill 從你的範本抽到哪些欄位（不打 LLM，純解析）
python -c "
import sys; sys.path.insert(0, '/home/jacktsai/.claude/skills/tw-call-memo/scripts')
from memo import infer_fields_from_template
from pathlib import Path
fields, aliases = infer_fields_from_template(Path('${HOME}/my_format.docx'))
for k, l, d in fields:
    print(f'  {l}')
print(f'\n共 {len(fields)} 個欄位')
"
```
