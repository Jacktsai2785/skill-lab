import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "compare_order.py"


class CompareOrderCliTests(unittest.TestCase):
    def run_cli(self, source, actual, *extra):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.json"
            actual_path = root / "actual.json"
            source_path.write_text(json.dumps(source), encoding="utf-8")
            actual_path.write_text(json.dumps(actual), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    str(source_path),
                    "--actual",
                    str(actual_path),
                    *extra,
                ],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_matching_explicit_order(self):
        rows = [
            {"id": "a", "display_order": 1},
            {"id": "b", "display_order": 2},
        ]
        result = self.run_cli(rows, rows)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "match")

    def test_source_row_order_and_mismatch(self):
        source = [{"id": "a"}, {"id": "b"}]
        actual = [
            {"id": "a", "display_order": 2},
            {"id": "b", "display_order": 1},
        ]
        result = self.run_cli(source, actual, "--source-row-order")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(json.loads(result.stdout)["order_mismatches"]), 2)

    def test_duplicate_id_is_invalid(self):
        source = [
            {"id": "a", "display_order": 1},
            {"id": "a", "display_order": 2},
        ]
        result = self.run_cli(source, [])
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate", json.loads(result.stdout)["error"])

    def test_empty_source_is_invalid(self):
        result = self.run_cli([], [{"id": "a", "display_order": 1}])
        self.assertEqual(result.returncode, 2)
        self.assertIn("no records", json.loads(result.stdout)["error"])

    def test_integral_float_id_matches_integer_json_id(self):
        source = [{"id": 1.0, "display_order": 1}]
        actual = [{"id": 1, "display_order": 1}]
        result = self.run_cli(source, actual)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
