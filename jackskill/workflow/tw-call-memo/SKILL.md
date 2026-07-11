---
name: tw-call-memo
description: >
  Generate a Taiwan PE/VC investment Call Memo from a meeting transcript or audio
  recording. Three-stage pipeline: (1) ingest transcript (text / .txt / .pdf / .docx)
  or transcribe audio via Whisper, (2) extract structured fields via Claude LLM
  using either the bundled 20-field schema or a user-supplied DOCX template, (3) emit
  JSON and optionally fill the template into a downloadable .docx.
  TRIGGER when: user uploads a transcript / 訪談逐字稿 / call recording and asks
  to generate a Call Memo / 訪談備忘錄 / 訪談紀錄, or says "幫我寫 call memo" /
  "整理逐字稿" / "把錄音轉成 memo" / "用這個範本填".
  DO NOT TRIGGER when: user only wants raw transcription (use whisper directly),
  needs PE-style due-diligence summary (use customer-intel / investment-research),
  or wants to identify companies from text (use tw-company-identify).
tags: [taiwan, pe-vc, llm, docx, whisper]
version: 1
source: manual
user_invocable: true
---

# Taiwan Call Memo

把任意逐字稿或錄音檔，轉成 PE/VC 投資 Call Memo（含 20 欄位 JSON + 可下載 Word 檔）。

## Pipeline

```
input ──► (1) Ingest ──────► (2) Extract ──────────► (3) Render ──► JSON + DOCX
         text/file/audio    Claude LLM 從逐字稿       填入 .docx 範本
                            抽取結構化欄位             (bundled 或自訂)
```

1. **Ingest** — 接受 `--text` / `--stdin` / `--file path.{txt,pdf,docx}` / `--audio path.{mp3,wav,m4a,...}`。音訊檔走 Whisper 轉成中文逐字稿。
2. **Extract** — Claude LLM 依指定 schema 從逐字稿抽出欄位；預設用內建 20 欄位（PE/VC 標準），或從 `--template` 推斷。
3. **Render** — 一定輸出 JSON 到 stdout；若加 `--docx OUTPUT`，同時把欄位填入範本並另存 Word 檔。

## Setup

```bash
# Core (text/file 模式必裝)
pip install -r ~/.claude/skills/tw-call-memo/scripts/requirements.txt

# Optional: 音訊轉逐字稿
pip install -r ~/.claude/skills/tw-call-memo/scripts/requirements-audio.txt
# Linux: sudo apt install ffmpeg
# macOS: brew install ffmpeg

# LLM
export ANTHROPIC_API_KEY=sk-ant-...
```

無 `ANTHROPIC_API_KEY` 時可加 `--provider cli` fallback 到本機 `claude` CLI（對長 prompt 較不穩定）。

## Usage

```bash
# 文字字串
python ~/.claude/skills/tw-call-memo/scripts/memo.py --company "台積電" --text "今天和副總開會..."

# stdin
cat transcript.txt | python ~/.claude/skills/tw-call-memo/scripts/memo.py --company "台積電" --stdin

# 檔案 (txt / pdf / docx)
python ~/.claude/skills/tw-call-memo/scripts/memo.py --company "台積電" --file meeting.pdf

# 音訊 (Whisper)
python ~/.claude/skills/tw-call-memo/scripts/memo.py --company "台積電" --audio call.mp3

# 同時輸出 Word 檔
python ~/.claude/skills/tw-call-memo/scripts/memo.py --company "台積電" --file t.txt --docx /tmp/memo.docx

# 自訂範本（自動推斷欄位）
python ~/.claude/skills/tw-call-memo/scripts/memo.py --company "台積電" --file t.txt \
  --template ~/my_format.docx --docx /tmp/out.docx

# 指定訪談日期 + 純 JSON 輸出
python ~/.claude/skills/tw-call-memo/scripts/memo.py --company "台積電" --file t.txt \
  --date 2025/05/04 --json-only
```

### Options

| flag | 說明 |
|------|------|
| `--company NAME` | **必填**，公司名（注入 prompt 給 LLM 上下文）|
| `--text TEXT` | 直接吃逐字稿字串 |
| `--stdin` | 從 stdin 讀逐字稿 |
| `--file PATH` | 讀 `.txt` / `.pdf` / `.docx` |
| `--audio PATH` | 讀音訊 (`mp3/wav/m4a/ogg/webm/flac/aac/wma/mp4`)，需 audio extras |
| `--template PATH` | 自訂 DOCX 範本；省略則用 bundled |
| `--docx OUTPUT` | 寫出填好的 .docx 到此路徑 |
| `--date YYYY/MM/DD` | 訪談日期，預設今天 |
| `--provider {anthropic,cli}` | 預設 `anthropic`；無 API key 時改 `cli` |
| `--whisper-model {tiny,base,small,medium,large}` | 預設 `small` |
| `--json-only` | 只輸出 JSON 到 stdout（壓 stderr summary）|

## Template Modes

### 1. Bundled (預設)
- 範本：`data/call_memo_template.docx`（從 taiwan-company 專案複製）
- 欄位：固定 20 個 PE/VC 標準欄位，英文 key（`deal_source`, `interviewees`, `paid_in_capital`, ...）
- 與 taiwan-company 的 `companies.json` `call_memo` 結構完全相容

### 2. Custom (`--template path/to/ref.docx`)
- skill 自動 walk 第一個 table 的所有 cells
- cell 第一行若以「：」結尾 → 視為 label 欄位
- label（去掉「：」）直接當 JSON key（中文）
- LLM prompt 動態產生
- 細節：[reference/template-inference.md](reference/template-inference.md)

## Output Schema

```json
{
  "company": "台積電",
  "interview_date": "2025/05/04",
  "template": "bundled",
  "transcript": null,
  "fields": {
    "deal_source": "自行開發",
    "interviewees": "副總 王大明",
    "paid_in_capital": "NT$ 5,000 萬",
    "...": "..."
  },
  "docx_output": "/tmp/memo.docx"
}
```

- `template`: `"bundled"` 或 `"custom: <path>"`
- `transcript`: 僅 `--audio` 模式才填（whisper 結果），其餘為 `null`
- `fields` keys：bundled 模式為英文，custom 模式為中文 label
- `docx_output`: 有 `--docx` 才填，否則 `null`

## Reference

- [reference/prompts.md](reference/prompts.md) — extract prompt 完整版
- [reference/template-inference.md](reference/template-inference.md) — 自訂範本如何被解析

## Related Skills

- **tw-company-identify** — 從文字/圖片辨識公司並抓官方資料；本 skill 不做公司辨識，只做訪談欄位抽取
- **tw-company-lookup** — 完整登記資料（findbiz 工廠/歷史/所營事業/經理人）
- **customer-intel** — B2B 客戶情蒐 + 銷售報告；call memo 完成後可接續做更深的客戶研究
- **investment-research** — 投資面研究與財報分析

## Troubleshooting

| 問題 | 解法 |
|------|------|
| `import whisper` 失敗 | `pip install -r scripts/requirements-audio.txt` 並另裝 ffmpeg |
| Whisper 跑很慢 / 第一次卡住 | 首次會下載模型（small ≈ 500MB）；可改用 `--whisper-model tiny` 加速 |
| `ANTHROPIC_API_KEY not set` | export key，或加 `--provider cli` 走本機 claude CLI |
| 自訂範本抽不到欄位 | 確認範本是「表格」結構、cell 第一行以「：」結尾；參考 [reference/template-inference.md](reference/template-inference.md) |
| PDF 解析空白 | 該 PDF 可能是純圖片；本 skill 不做 OCR，請先用其他工具轉文字 |
| DOCX 輸出 cell 沒填到 | label 必須與範本完全一致（含全形「：」）；自訂範本下 LLM 回的中文 key 也要與 label 對得上 |
| 逐字稿過長被截掉 | 目前固定取前 12,000 字（與原專案一致）；超長內容請呼叫端先分段 |
| `claude` CLI fallback 失敗 | 改設 `ANTHROPIC_API_KEY` 走 SDK；CLI 對長 prompt 較不穩定 |

## Notes

- **不維護 state**：每次呼叫 stateless；要寫回資料庫請呼叫端自理。
- **不做 OCR / Excel**：場景少用；如需請先用其他工具轉成文字。
- **Provider**：v1 只支援 Anthropic SDK + claude CLI fallback（與 sibling skills 對齊），不含 OpenAI/Gemini。
- **Prompt 與 FIELDS 規則**逐字保留自 [taiwan-company](https://github.com/) 的 `services/memo_extractor.py`，跨專案行為一致。
