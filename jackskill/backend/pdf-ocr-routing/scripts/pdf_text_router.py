#!/usr/bin/env python3
"""Extract PDF text page by page with OCR fallback."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


class ExtractionError(RuntimeError):
    """Base error for extraction failures."""


class EncryptedPdfError(ExtractionError):
    """Raised when a PDF requires a password."""


class PageLimitError(ExtractionError):
    """Raised before processing a PDF that exceeds the configured page limit."""


@dataclass(frozen=True)
class PageResult:
    page: int
    source: str
    characters: int
    text: str


def extract_pages(
    reader: Any,
    ocr_page: Callable[[int], str],
    *,
    min_native_chars: int = 20,
    max_pages: int = 200,
) -> list[PageResult]:
    if getattr(reader, "is_encrypted", False):
        raise EncryptedPdfError("PDF is encrypted; provide a decrypted input")
    page_count = len(reader.pages)
    if page_count == 0:
        raise ExtractionError("PDF contains no pages")
    if page_count > max_pages:
        raise PageLimitError(f"PDF has {page_count} pages; limit is {max_pages}")

    results: list[PageResult] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            native = page.extract_text() or ""
        except Exception as exc:
            raise ExtractionError(
                f"page {index}: native text extraction failed: {exc}"
            ) from exc
        if len("".join(native.split())) >= min_native_chars:
            text, source = native, "native"
        else:
            text, source = ocr_page(index) or "", "ocr"
            if not text.strip():
                raise ExtractionError(f"page {index}: OCR returned no text")
        results.append(
            PageResult(
                page=index,
                source=source,
                characters=len(text),
                text=text,
            )
        )
    return results


def open_reader(path: Path) -> Any:
    try:
        import pypdf
    except ImportError as exc:
        raise ExtractionError("PDF parsing requires: pip install pypdf") from exc
    try:
        return pypdf.PdfReader(path)
    except Exception as exc:
        raise ExtractionError(f"cannot parse PDF: {exc}") from exc


def build_tesseract_ocr(
    path: Path, *, languages: str, dpi: int
) -> Callable[[int], str]:
    def ocr_page(page_number: int) -> str:
        try:
            import pytesseract
            from pdf2image import convert_from_path
        except ImportError as exc:
            raise ExtractionError(
                "OCR requires: pip install pdf2image pytesseract"
            ) from exc
        try:
            images = convert_from_path(
                path,
                dpi=dpi,
                first_page=page_number,
                last_page=page_number,
            )
            if len(images) != 1:
                raise ExtractionError(
                    f"page {page_number}: renderer returned {len(images)} images"
                )
            return pytesseract.image_to_string(images[0], lang=languages)
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError(f"page {page_number}: OCR failed: {exc}") from exc

    return ocr_page


def render_text(results: list[PageResult]) -> str:
    sections = [
        f"--- page {result.page} ({result.source}) ---\n{result.text.rstrip()}"
        for result in results
    ]
    return "\n\n".join(sections) + "\n"


def render_report(path: Path, results: list[PageResult]) -> None:
    payload = {
        "status": "success",
        "pages": [
            {key: value for key, value in asdict(result).items() if key != "text"}
            for result in results
        ],
        "native_pages": sum(result.source == "native" for result in results),
        "ocr_pages": sum(result.source == "ocr" for result in results),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--languages", default="eng")
    parser.add_argument("--min-native-chars", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args(argv)
    if args.min_native_chars < 1:
        parser.error("--min-native-chars must be positive")
    if args.max_pages < 1:
        parser.error("--max-pages must be positive")
    if not 72 <= args.dpi <= 600:
        parser.error("--dpi must be between 72 and 600")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        reader = open_reader(args.pdf)
        results = extract_pages(
            reader,
            build_tesseract_ocr(args.pdf, languages=args.languages, dpi=args.dpi),
            min_native_chars=args.min_native_chars,
            max_pages=args.max_pages,
        )
        text = render_text(results)
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        if args.report:
            render_report(args.report, results)
    except (ExtractionError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
