#!/usr/bin/env python3
"""Preview or apply safe personal-workspace initialization and archival."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


ASSET_ROOT = Path(__file__).parents[1] / "assets" / "vault"
POLICIES = {
    "decisions": {"age_days": 365, "statuses": set()},
    "interviews": {"age_days": 730, "statuses": {"rejected", "no_response"}},
    "meetings": {"age_days": 180, "statuses": set()},
}


class WorkspaceError(RuntimeError):
    """Raised when an operation cannot be completed without data risk."""


@dataclass(frozen=True)
class Move:
    source: str
    destination: str
    reason: str


def files_to_copy(target: Path) -> list[tuple[Path, Path]]:
    return [
        (source, target / source.relative_to(ASSET_ROOT))
        for source in sorted(ASSET_ROOT.rglob("*"))
        if source.is_file()
    ]


def init_workspace(target: Path, *, apply: bool, merge: bool) -> dict:
    target = target.expanduser().resolve()
    if target == Path(target.anchor):
        raise WorkspaceError("refusing to initialize a filesystem root")
    if target.exists() and any(target.iterdir()) and not merge:
        raise WorkspaceError("target is non-empty; review it and use --merge")
    copies = files_to_copy(target)
    collisions = [str(destination) for _, destination in copies if destination.exists()]
    if collisions:
        raise WorkspaceError(f"refusing to overwrite existing files: {collisions}")

    planned = [str(destination) for _, destination in copies]
    if apply:
        for source, destination in copies:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        (target / ".metadata").mkdir(parents=True, exist_ok=True)
    return {"status": "applied" if apply else "preview", "files": planned}


def parse_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise WorkspaceError("missing YAML frontmatter")
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return values
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip("\"'")
    raise WorkspaceError("unterminated YAML frontmatter")


def plan_archive(target: Path, *, today: date | None = None) -> tuple[list[Move], list[dict]]:
    target = target.expanduser().resolve()
    today = today or date.today()
    moves: list[Move] = []
    skipped: list[dict] = []

    for category, policy in POLICIES.items():
        category_root = target / category
        if not category_root.exists():
            continue
        for source in sorted(category_root.rglob("*.md")):
            if source.name == "README.md":
                continue
            if source.is_symlink():
                skipped.append({"source": str(source), "reason": "symbolic link"})
                continue
            try:
                metadata = parse_frontmatter(source)
                status = metadata.get("status", "")
                raw_date = metadata.get("date")
                if not raw_date:
                    raise WorkspaceError("missing frontmatter date")
                note_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except (OSError, UnicodeError, ValueError, WorkspaceError) as exc:
                skipped.append({"source": str(source), "reason": str(exc)})
                continue

            age_days = (today - note_date).days
            status_match = status in policy["statuses"]
            age_match = age_days > policy["age_days"]
            if not (status_match or age_match):
                continue
            relative = source.relative_to(category_root)
            destination = target / "archive" / category / relative
            if destination.exists():
                raise WorkspaceError(f"archive destination exists: {destination}")
            reason = f"status={status}" if status_match else f"age_days={age_days}"
            moves.append(Move(str(source), str(destination), reason))
    return moves, skipped


def archive_workspace(target: Path, *, apply: bool) -> dict:
    target = target.expanduser().resolve()
    moves, skipped = plan_archive(target)
    if apply:
        log_path = target / ".metadata" / "archive-log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            for move in moves:
                source = Path(move.source)
                destination = Path(move.destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise WorkspaceError(f"archive destination exists: {destination}")
                shutil.move(str(source), str(destination))
                log.write(
                    json.dumps(
                        {
                            **asdict(move),
                            "applied_at": datetime.now().astimezone().isoformat(),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    return {
        "status": "applied" if apply else "preview",
        "moves": [asdict(move) for move in moves],
        "skipped": skipped,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("target", type=Path)
    init_parser.add_argument("--apply", action="store_true")
    init_parser.add_argument("--merge", action="store_true")

    archive_parser = subparsers.add_parser("archive")
    archive_parser.add_argument("target", type=Path)
    archive_parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "init":
            report = init_workspace(args.target, apply=args.apply, merge=args.merge)
        else:
            report = archive_workspace(args.target, apply=args.apply)
    except (WorkspaceError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
