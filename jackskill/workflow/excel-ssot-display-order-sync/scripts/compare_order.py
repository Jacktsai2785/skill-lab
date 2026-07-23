#!/usr/bin/env python3
"""Compare source-of-truth display order with an exported actual state."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


class InputError(ValueError):
    """Raised when an input cannot be compared safely."""


def _unwrap_json(value: Any, json_key: str | None) -> list[dict[str, Any]]:
    if json_key:
        if not isinstance(value, dict) or json_key not in value:
            raise InputError(f"JSON key {json_key!r} was not found")
        value = value[json_key]
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise InputError("JSON input must be an array of objects")
    return value


def load_records(
    path: Path, *, sheet: str | None = None, json_key: str | None = None
) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open(encoding="utf-8") as handle:
            return _unwrap_json(json.load(handle), json_key)
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".xlsx":
        try:
            import openpyxl
        except ImportError as exc:
            raise InputError("reading .xlsx requires: pip install openpyxl") from exc
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            worksheet = workbook[sheet] if sheet else workbook.active
            rows = worksheet.iter_rows(values_only=True)
            headers = next(rows, None)
            if not headers:
                raise InputError("workbook contains no header row")
            names = [
                str(value).strip() if value is not None else "" for value in headers
            ]
            if not all(names) or len(names) != len(set(names)):
                raise InputError("header names must be non-empty and unique")
            return [dict(zip(names, row, strict=True)) for row in rows]
        finally:
            workbook.close()
    raise InputError(f"unsupported input type: {suffix or '<none>'}")


def normalize_id(value: Any, *, field: str, row_number: int) -> str:
    if value is None or str(value).strip() == "":
        raise InputError(f"row {row_number}: blank {field!r}")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_order(value: Any, *, field: str, row_number: int) -> int:
    if isinstance(value, bool) or value is None or str(value).strip() == "":
        raise InputError(f"row {row_number}: invalid {field!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InputError(f"row {row_number}: {field!r} is not numeric") from exc
    if not number.is_integer():
        raise InputError(f"row {row_number}: {field!r} must be an integer")
    return int(number)


def build_order_map(
    records: list[dict[str, Any]],
    *,
    id_field: str,
    order_field: str,
    row_order: bool,
) -> dict[str, int]:
    if not records:
        raise InputError("input contains no records")
    result: dict[str, int] = {}
    for row_number, record in enumerate(records, start=2):
        if id_field not in record:
            raise InputError(f"row {row_number}: missing {id_field!r}")
        record_id = normalize_id(record[id_field], field=id_field, row_number=row_number)
        if record_id in result:
            raise InputError(f"duplicate {id_field!r}: {record_id!r}")
        if row_order:
            order = row_number - 1
        else:
            if order_field not in record:
                raise InputError(f"row {row_number}: missing {order_field!r}")
            order = normalize_order(
                record[order_field], field=order_field, row_number=row_number
            )
        result[record_id] = order
    return result


def compare(source: dict[str, int], actual: dict[str, int]) -> dict[str, Any]:
    missing = sorted(source.keys() - actual.keys())
    unexpected = sorted(actual.keys() - source.keys())
    mismatches = [
        {"id": record_id, "expected": source[record_id], "actual": actual[record_id]}
        for record_id in sorted(source.keys() & actual.keys())
        if source[record_id] != actual[record_id]
    ]
    return {
        "status": "match" if not (missing or unexpected or mismatches) else "mismatch",
        "source_count": len(source),
        "actual_count": len(actual),
        "missing_ids": missing,
        "unexpected_ids": unexpected,
        "order_mismatches": mismatches,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--id-field", default="id")
    parser.add_argument("--order-field", default="display_order")
    parser.add_argument("--source-row-order", action="store_true")
    parser.add_argument("--source-sheet")
    parser.add_argument("--source-json-key")
    parser.add_argument("--actual-json-key")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        source_records = load_records(
            args.source, sheet=args.source_sheet, json_key=args.source_json_key
        )
        actual_records = load_records(args.actual, json_key=args.actual_json_key)
        source = build_order_map(
            source_records,
            id_field=args.id_field,
            order_field=args.order_field,
            row_order=args.source_row_order,
        )
        actual = build_order_map(
            actual_records,
            id_field=args.id_field,
            order_field=args.order_field,
            row_order=False,
        )
        report = compare(source, actual)
    except (InputError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "match" else 1


if __name__ == "__main__":
    sys.exit(main())
