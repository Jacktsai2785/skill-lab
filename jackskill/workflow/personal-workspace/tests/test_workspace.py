import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "workspace.py"
SPEC = importlib.util.spec_from_file_location("personal_workspace", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class WorkspaceTests(unittest.TestCase):
    def test_init_preview_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "vault"
            report = MODULE.init_workspace(target, apply=False, merge=False)
            self.assertEqual(report["status"], "preview")
            self.assertFalse(target.exists())

    def test_init_apply_creates_files_not_readme_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "vault"
            MODULE.init_workspace(target, apply=True, merge=False)
            self.assertTrue((target / "README.md").is_file())
            self.assertTrue((target / "notes" / "README.md").is_file())
            self.assertFalse((target / "notes" / "README").exists())

    def test_archive_uses_frontmatter_date_recursively(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            note = target / "decisions" / "2020" / "old.md"
            note.parent.mkdir(parents=True)
            note.write_text(
                "---\ntitle: Old\ndate: 2020-01-01\nstatus: active\n---\n",
                encoding="utf-8",
            )
            moves, skipped = MODULE.plan_archive(target, today=date(2026, 1, 1))
            self.assertEqual(skipped, [])
            self.assertEqual(len(moves), 1)
            self.assertTrue(moves[0].destination.endswith("archive/decisions/2020/old.md"))

    def test_archive_preview_does_not_move(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            note = target / "interviews" / "company" / "candidate.md"
            note.parent.mkdir(parents=True)
            note.write_text(
                "---\ntitle: Candidate\ndate: 2026-01-01\nstatus: rejected\n---\n",
                encoding="utf-8",
            )
            report = MODULE.archive_workspace(target, apply=False)
            self.assertEqual(len(report["moves"]), 1)
            self.assertTrue(note.exists())

    def test_archive_skips_symbolic_links(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            outside = target / "outside.md"
            outside.write_text(
                "---\ntitle: Outside\ndate: 2020-01-01\nstatus: active\n---\n",
                encoding="utf-8",
            )
            link = target / "decisions" / "linked.md"
            link.parent.mkdir(parents=True)
            link.symlink_to(outside)
            moves, skipped = MODULE.plan_archive(target, today=date(2026, 1, 1))
            self.assertEqual(moves, [])
            self.assertEqual(skipped[0]["reason"], "symbolic link")


if __name__ == "__main__":
    unittest.main()
