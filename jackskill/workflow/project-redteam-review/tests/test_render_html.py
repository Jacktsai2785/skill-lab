import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_html.py"


def sample_data():
    return {
        "meta": {
            "project": "測試專案",
            "date": "2026-07-23",
            "type": "CLI",
            "dimensions": ["正確性"],
            "applied": False,
        },
        "teams": [],
        "findings": [
            {
                "team": "對抗者",
                "category": "技術健康",
                "severity": "高",
                "location": "src/main.py:1",
                "problem": "<!--<script src='legacy.js'></script>",
                "suggestion": "修正",
                "confidence": "高",
                "evidence": "src/main.py:1 可直接重現",
            }
        ],
        "conflicts": [],
        "before_after": [],
        "actions": [],
        "_context": {"manifest": "manifest", "fact_base": "facts"},
    }


class RenderHtmlCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_consume_export_and_applied_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "REDTEAM-REVIEW.json"
            html = root / "REDTEAM-REVIEW.html"
            exported = root / "restored.json"
            source.write_text(
                json.dumps(sample_data(), ensure_ascii=False),
                encoding="utf-8",
            )

            self.run_cli(source, "--consume", "--no-open")
            self.assertFalse(source.exists())
            self.assertTrue(html.exists())
            html_text = html.read_text(encoding="utf-8")
            self.assertNotIn("<!--<script", html_text)
            self.assertNotIn("<script src='legacy.js'>", html_text)
            self.assertIn("\\u003c!--\\u003cscript", html_text)
            self.assertIn("信心 高", html_text)
            self.assertIn("src/main.py:1 可直接重現", html_text)

            self.run_cli(html, "--export-json", exported)
            restored = json.loads(exported.read_text(encoding="utf-8"))
            self.assertEqual(restored, sample_data())

            applied_json = root / "applied.json"
            self.run_cli(html, "--applied", "--export-json", applied_json)
            applied = json.loads(applied_json.read_text(encoding="utf-8"))
            self.assertTrue(applied["meta"]["applied"])

            self.run_cli(applied_json, "--consume", "--no-open")
            self.assertFalse(applied_json.exists())

    def test_rejects_html_without_embedded_report_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "other.html"
            source.write_text("<html></html>", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(source), "--no-open"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("redteam-source", result.stderr)


if __name__ == "__main__":
    unittest.main()
