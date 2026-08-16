import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "collab_transcript", SCRIPT_DIR / "collab_transcript.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TranscriptTerminalHandoffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "ledger.db"
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        con = sqlite3.connect(self.ledger)
        con.executescript(
            """
            CREATE TABLE runs (run_id TEXT PRIMARY KEY, status TEXT NOT NULL);
            CREATE TABLE model_calls (
              run_id TEXT, call_id TEXT, adapter TEXT, role TEXT, status TEXT,
              output_artifact_id TEXT, attempt_count INTEGER,
              idempotency_key TEXT, started_at TEXT, committed_at TEXT
            );
            CREATE TABLE audit_events (
              run_id TEXT, event_type TEXT, actor TEXT,
              payload_redacted_json TEXT, created_at TEXT
            );
            CREATE TABLE decision_cards (
              run_id TEXT, card_id TEXT, trigger TEXT, question TEXT,
              why_now TEXT, options_json TEXT, recommended_option_id TEXT,
              recommendation_reasoning TEXT, status TEXT, created_at TEXT
            );
            CREATE TABLE artifacts (
              run_id TEXT, artifact_id TEXT, kind TEXT, created_at TEXT
            );
            CREATE TABLE ac_results (
              run_id TEXT, criterion_ref TEXT, criticality TEXT,
              status TEXT, detail_json TEXT
            );
            """
        )
        con.close()
        self.module = load_module()
        self.module.LEDGER = self.ledger
        self.module.ARTIFACTS = self.artifacts
        self.module.DASHBOARD_URL = "http://127.0.0.1:8787/?run=run-test"

    def tearDown(self):
        self.tmp.cleanup()

    def insert_run(self, status):
        con = sqlite3.connect(self.ledger)
        con.execute("INSERT INTO runs VALUES (?, ?)", ("run-test", status))
        con.commit()
        con.close()

    def test_active_run_keeps_refresh_without_delivery_dialog(self):
        self.insert_run("revising")

        page = self.module.build("run-test", "測試主題")

        self.assertIn('http-equiv="refresh"', page)
        self.assertNotIn("<dialog class='completion-dialog'", page)
        self.assertIn("run 仍在背景執行", page)

    def test_terminal_run_stops_refresh_and_delivers_outcome_in_same_tab(self):
        self.insert_run("completed_with_unverified_hard_ac")
        con = sqlite3.connect(self.ledger)
        con.execute(
            "INSERT INTO ac_results VALUES (?, ?, ?, ?, ?)",
            (
                "run-test",
                "ac-source-inspection",
                "hard",
                "partially_satisfied",
                '{"explanation":"來源尚未逐檔驗證",'
                '"test_recommendation":"執行 G0 source inspection"}',
            ),
        )
        con.executemany(
            "INSERT INTO ac_results VALUES (?, ?, ?, ?, ?)",
            [
                (
                    "run-test", "ac-security", "hard", "accepted_risk",
                    '{"explanation":"使用者已接受殘留風險"}',
                ),
                (
                    "run-test", "ac-responsive", "soft", "partially_satisfied",
                    '{"explanation":"仍需實機視覺測試"}',
                ),
                (
                    "run-test", "ac-workflow", "hard", "satisfied",
                    '{"explanation":"核心流程已覆蓋"}',
                ),
            ],
        )
        con.commit()
        con.close()

        page = self.module.build("run-test", "測試主題")

        self.assertNotIn('http-equiv="refresh"', page)
        self.assertIn("completion-dialog", page)
        self.assertIn("本輪規劃流程已完成", page)
        self.assertIn("以下是進入實作前的驗證清單", page)
        self.assertIn("來源尚未逐檔驗證", page)
        self.assertIn("執行 G0 source inspection", page)
        self.assertIn("1 項硬性驗收需在實作前補證", page)
        self.assertIn("另有 1 項已接受風險、1 項軟性驗證建議", page)
        self.assertIn("硬性驗收待補證（1）", page)
        self.assertIn("已接受風險（1）", page)
        self.assertIn("軟性驗證建議（1）", page)
        self.assertNotIn("4 項完成條件仍需後續驗證", page)
        self.assertNotIn("ac-workflow</strong>", page)
        self.assertIn("href='./run-test.html'", page)
        self.assertIn("本輪已停止自動刷新", page)
        self.assertNotIn("run 仍在背景執行", page)

    def test_watcher_builds_report_before_final_render(self):
        script = (SCRIPT_DIR / "watch_transcript.sh").read_text(encoding="utf-8")
        terminal_branch = script.split(
            'grep -qE "completed|cancelled|escalated|failed"', 1
        )[1]

        self.assertLess(
            terminal_branch.index('report "$RUN_ID" --format html'),
            terminal_branch.index("\n    render"),
        )


if __name__ == "__main__":
    unittest.main()
