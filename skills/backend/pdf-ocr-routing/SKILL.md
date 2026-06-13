---
name: pdf-ocr-routing
description: 自動偵測 PDF 類型（text-based 或 scanned），決定文字抽取路線以避免 silent failure。TRIGGER when: 「PDF 抽不到文字」「OCR 抓不到」「差異分析報告（共 0 筆）」「掃描檔差異」「PDF 類型偵測」
when_to_use: 差異分析或文字抽取 pipeline 發現空陣列輸出，或使用者明確指出 PDF 無法讀取
version: 1.0.0
tags:
  - pdf
  - ocr
  - routing
  - text-extraction
  - automation
languages: all
---

## Overview

PDF 文字抽取任務中，最常見的 silent failure 是：**pypdf 對掃描檔（image-based PDF）傳回空字串，而使用者察覺不到根本原因**。這導致差異分析報告輸出「共 0 筆」，看起來像是資料問題而不是技術缺陷。

`pdf-ocr-routing` 在處理 PDF 前自動分流：
1. **Text-based PDF**（可直接提取文字）→ 用 `pypdf` 直讀，快速高效
2. **Scanned PDF**（純圖檔，無可提取文字）→ 用 `tesseract` / `paddleocr` OCR，確保內容不會遺失

這個 skill 關閉了既有 `file-diff-agent` 中的缺口（完全沒有 PDF 類型分流邏輯），避免重複遇到「抽文字失敗但沒人發現」的問題。

## 何時使用

**具體場景：**
- 使用者上傳 PDF 進行差異分析，報告顯示「共 0 筆差異」或「無法提取文字」
- 已知某個 PDF 是掃描檔，但走 text-extraction pipeline 時失敗
- `pdftotext` 或 `pypdf` 對某個檔案傳回空字串，但檔案實際上包含可讀內容
- 需要建構一個「PDF 輸入無感知」的差異分析服務（不讓使用者判斷格式）

**信號詞匯：**
- 「PDF 抽不到文字」
- 「OCR 抓不到」
- 「差異分析報告（共 0 筆）」
- 「掃描檔差異」
- 「PDF 格式判斷」
- 「為什麼沒有結果」

## 執行步驟

### Step 1：PDF 類型偵測邏輯

在差異分析 pipeline 的入口，加入 PDF 類型檢查：

```python
import pypdf
import os

def detect_pdf_type(pdf_path: str) -> str:
    """
    傳回 'text-based' 或 'scanned'
    
    邏輯：嘗試用 pypdf 提取文字。
    如果提取的文字量 < 5%（相對於 PDF 大小），
    判定為 scanned；否則判定為 text-based。
    """
    try:
        with open(pdf_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            full_text = ''.join(
                page.extract_text() for page in reader.pages
            )
        
        # 粗略啟發式：如果文字量太少，視為掃描檔
        # （通常掃描檔會完全 extract 為空，text-based 至少有幾 KB）
        file_size_kb = os.path.getsize(pdf_path) / 1024
        text_length = len(full_text.strip())
        
        # 如果提取文字 < 100 字 + 檔案 > 100 KB，視為掃描檔
        if text_length < 100 and file_size_kb > 100:
            return 'scanned'
        elif text_length == 0:
            return 'scanned'
        else:
            return 'text-based'
    except Exception as e:
        # 讀取失敗時預設為 scanned（較安全的假設）
        return 'scanned'
```

### Step 2：文字抽取路由

根據偵測結果選擇抽取方式：

```python
def extract_text_with_routing(pdf_path: str) -> str:
    """
    依 PDF 類型自動路由到不同的文字抽取工具
    """
    pdf_type = detect_pdf_type(pdf_path)
    
    if pdf_type == 'text-based':
        # 直接用 pypdf，速度快
        return extract_text_pypdf(pdf_path)
    else:
        # 用 OCR，處理掃描檔
        return extract_text_ocr(pdf_path)

def extract_text_pypdf(pdf_path: str) -> str:
    """直接文字抽取，用於 text-based PDF"""
    with open(pdf_path, 'rb') as f:
        reader = pypdf.PdfReader(f)
        text = ''.join(
            page.extract_text() for page in reader.pages
        )
    return text

def extract_text_ocr(pdf_path: str) -> str:
    """
    用 OCR 抽取，用於掃描檔。
    
    優先使用 PaddleOCR（中文支援好，速度快），
    fallback 到 Tesseract（通用性強）
    """
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang=['ch', 'en'])
        # 先將 PDF 轉為圖片
        images = pdf_to_images(pdf_path)
        full_text = []
        for img in images:
            results = ocr.ocr(img, cls=True)
            page_text = '\n'.join(
                line[1][0] for line in results if line
            )
            full_text.append(page_text)
        return '\n'.join(full_text)
    except ImportError:
        # fallback to Tesseract
        return extract_text_tesseract(pdf_path)

def extract_text_tesseract(pdf_path: str) -> str:
    """Tesseract fallback（需先轉 PDF → 圖片）"""
    import pytesseract
    images = pdf_to_images(pdf_path)
    full_text = []
    for img in images:
        text = pytesseract.image_to_string(img, lang='chi_tra+eng')
        full_text.append(text)
    return '\n'.join(full_text)

def pdf_to_images(pdf_path: str):
    """將 PDF 轉為圖片列表（用於 OCR）"""
    from pdf2image import convert_from_path
    return convert_from_path(pdf_path, dpi=150)
```

### Step 3：整合到差異分析 pipeline

修改既有的 `file-diff-agent` 或差異分析入口：

```python
def analyze_pdf_diff(pdf1_path: str, pdf2_path: str) -> dict:
    """
    差異分析的新入口，自動偵測 PDF 類型並路由
    """
    # 先各自抽取文字（自動路由）
    text1 = extract_text_with_routing(pdf1_path)
    text2 = extract_text_with_routing(pdf2_path)
    
    # 檢查是否都抽到文字
    if not text1.strip() or not text2.strip():
        return {
            'status': 'warning',
            'message': '無法從一或兩個 PDF 提取文字（可能格式不支援）',
            'diffs': []
        }
    
    # 進行文字差異分析（既有邏輯）
    diffs = compute_diffs(text1, text2)
    
    return {
        'status': 'success',
        'pdf1_type': detect_pdf_type(pdf1_path),
        'pdf2_type': detect_pdf_type(pdf2_path),
        'diffs': diffs,
        'count': len(diffs)
    }
```

### Step 4：測試檢查清單

在部署前驗證：

1. **Text-based PDF**：用 `extract_text_with_routing()` 讀一份純文字 PDF，確認 `pypdf` 路線被選中且文字正確抽取
2. **Scanned PDF**：用同一函數讀一份掃描檔，確認 OCR 路線被選中且內容被正確識別
3. **混合型 PDF**：部分頁面是文字、部分頁面是圖片的 PDF，檢查是否能正確判定為 `scanned`（較保守的做法）
4. **Empty PDF**：完全空白的 PDF，確認被判定為 `scanned` 而不拋出例外
5. **差異分析結果**：用上述 3 種 PDF 進行差異分析，確認輸出不再是「共 0 筆」

## 注意事項

### 效能考量
- **Tesseract / PaddleOCR 很慢**：掃描檔 OCR 處理單頁可能需要數秒。建議在背景任務中執行，或對大檔案按頁平行化。
- **PaddleOCR 首次執行會下載模型**：約 150 MB，可能需要 30 秒。部署時確保網路暢通或預先下載。

### 中文支援
- **Tesseract 中文能力有限**：建議優先使用 `paddleocr`（已內建繁體中文 `chi_tra`）。
- **PaddleOCR 預設模型是簡體**：如果需要繁體中文最佳效果，可下載繁體模型或設定 `lang=['ch']` 後補充繁體語言包。

### 已知限制
1. **PDF 類型偵測啟發式（< 100 字判定為 scanned）可能有誤判**：如果 text-based PDF 的實際內容確實 < 100 字，會被誤判為 scanned 後走 OCR。可根據實務調整閾值。
2. **掃描檔背景嘈雜時 OCR 準度下降**：特別是手機拍攝的模糊 PDF，效果會差。
3. **版面複雜的 PDF（表格、多欄位）**：OCR 可能亂序輸出。建議搭配版面分析工具（如 `layoutparser`）以取得更好結果，但會進一步增加延遲。

### 與既有 skills 的協作
- **file-diff-agent**：應在其內部集成 `extract_text_with_routing()`，而不是在外層調用。
- **audit-fix** 等依賴差異分析的 skills：受惠於更準確的文字抽取結果，應自動獲得改善。

---