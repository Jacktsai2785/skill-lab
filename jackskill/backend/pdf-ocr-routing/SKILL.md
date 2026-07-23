---
name: pdf-ocr-routing
description: >-
  Extract text from text, scanned, and mixed PDFs with page-level OCR fallback
  and explicit failure states. Use when PDF extraction returns blank or partial
  text, a scanned document needs OCR, or a PDF comparison reports suspiciously
  empty results. Do not treat encrypted, corrupt, unsupported, or truly empty
  PDFs as scanned documents.
---

# Route PDF extraction page by page

Prevent silent loss by deciding at page granularity. Preserve native text when
available and OCR only pages without enough extractable text.

## Workflow

1. Confirm the input path, expected language, output format, page count, and
   acceptable OCR cost.
2. Inspect the PDF parser result before OCR:

   - report encrypted files as `encrypted`;
   - report parser failures as `corrupt_or_unsupported`;
   - report zero-page documents as `empty`;
   - enforce a page limit before rendering images.

3. Run the bundled router:

   ```bash
   python3 scripts/pdf_text_router.py document.pdf \
     --languages chi_tra+eng \
     --output document.txt \
     --report document.extraction.json
   ```

   After confirming environment changes are allowed, install optional runtime
   dependencies only when needed:

   ```bash
   python3 -m pip install pypdf pdf2image pytesseract
   ```

   Tesseract and Poppler are separate system packages.

4. Review the JSON report. Each page records `native` or `ocr`; blank OCR output
   is a failure, not a successful empty page.
5. For comparison workflows, require usable text from both inputs before
   computing differences. Keep extraction warnings alongside the result.
6. Spot-check representative pages, including every page routed through OCR.

## Routing rules

- Convert `page.extract_text()` values of `None` to an empty string.
- Use native text when its non-whitespace length meets the threshold.
- OCR only the insufficient page, not the whole document.
- Never catch every parser exception and relabel it as `scanned`.
- Preserve page boundaries in output for traceability.
- Bound `--max-pages` and rendering DPI to prevent accidental resource
  exhaustion.

## Gotchas

- A mixed PDF can contain rich text on one page and a scanned image on the next;
  whole-document thresholds lose the scanned page.
- Short native pages can be legitimate. Adjust `--min-native-chars` based on the
  document, then inspect the report.
- OCR may scramble tables and columns. Use a layout-aware pipeline when reading
  order matters.
- OCR output is evidence requiring spot checks, not guaranteed ground truth.

## Resources

Run [scripts/pdf_text_router.py](scripts/pdf_text_router.py) for extraction. Its
core routing functions accept injected reader and OCR implementations so tests
do not require external PDF/OCR packages.
