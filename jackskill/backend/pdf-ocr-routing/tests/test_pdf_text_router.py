import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "pdf_text_router.py"
SPEC = importlib.util.spec_from_file_location("pdf_text_router", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class BrokenPage:
    def extract_text(self):
        raise RuntimeError("parser failed")


class FakeReader:
    def __init__(self, texts, *, encrypted=False):
        self.pages = [FakePage(text) for text in texts]
        self.is_encrypted = encrypted


class PdfTextRouterTests(unittest.TestCase):
    def test_mixed_pdf_routes_only_blank_page_to_ocr(self):
        calls = []

        def ocr(page_number):
            calls.append(page_number)
            return "scanned page text"

        results = MODULE.extract_pages(
            FakeReader(["native text is long enough", None]),
            ocr,
            min_native_chars=10,
        )
        self.assertEqual([result.source for result in results], ["native", "ocr"])
        self.assertEqual(calls, [2])

    def test_encrypted_pdf_is_not_relabelled_as_scanned(self):
        with self.assertRaises(MODULE.EncryptedPdfError):
            MODULE.extract_pages(FakeReader(["text"], encrypted=True), lambda _: "")

    def test_page_limit_fails_before_ocr(self):
        with self.assertRaises(MODULE.PageLimitError):
            MODULE.extract_pages(
                FakeReader(["one", "two"]),
                lambda _: "ocr",
                max_pages=1,
            )

    def test_blank_ocr_is_failure(self):
        with self.assertRaises(MODULE.ExtractionError):
            MODULE.extract_pages(
                FakeReader([None]),
                lambda _: " ",
                min_native_chars=1,
            )

    def test_native_page_error_has_page_context(self):
        reader = FakeReader([])
        reader.pages = [BrokenPage()]
        with self.assertRaisesRegex(MODULE.ExtractionError, "page 1"):
            MODULE.extract_pages(reader, lambda _: "ocr")


if __name__ == "__main__":
    unittest.main()
