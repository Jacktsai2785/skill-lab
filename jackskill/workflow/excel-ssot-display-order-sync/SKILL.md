---
name: excel-ssot-display-order-sync
description: >-
  Audit and synchronize display order from an Excel, CSV, or JSON source of
  truth through database, API, and frontend layers. Use when UI order differs
  from the source file, display_order is missing or duplicated, or frontend
  sorting overrides backend order. Do not use until the authoritative source,
  stable record ID, and ordering semantics are confirmed.
---

# Synchronize display order from a file SSOT

Preserve one ordering authority from the source file through every downstream
layer. Never derive a replacement order from an unordered database query.

## Workflow

1. Confirm the source file, worksheet, stable ID field, and order semantics:
   explicit `display_order` values or physical row order. Do not mix them.
2. Export the current DB or API state as JSON or CSV with the same stable ID.
3. Run a read-only comparison before writing:

   ```bash
   python3 scripts/compare_order.py \
     --source data/items.xlsx \
     --actual current-api.json \
     --id-field id \
     --order-field display_order
   ```

   Add `--source-row-order` only when physical Excel row order is authoritative.
   The command exits nonzero for duplicates, missing IDs, invalid order values,
   or mismatches.

4. Present counts and representative mismatches. Stop if either side contains
   duplicate IDs, missing IDs, or ambiguous blank order values.
5. Implement the project-specific write in one transaction:

   - stage normalized `(stable_id, display_order)` values;
   - update by stable ID;
   - reject missing and unexpected records unless policy explicitly permits them;
   - enforce uniqueness when the domain requires it;
   - roll back on any failed invariant.

6. Order API queries explicitly by `display_order` and a stable tie-breaker such
   as primary key. Do not rely on database default row order.
7. Remove only frontend sorts that contradict the SSOT. Preserve user-selected
   interactive sorting and document when it intentionally overrides default
   display order.
8. Verify Excel → DB → API → frontend with the same ID sequence. Check caches
   only after confirming the stored and API sequences are correct.

## Implementation rules

- Choose SQL for the project's actual database. Read
  [references/database-patterns.md](references/database-patterns.md) before
  writing a migration or backfill.
- Treat `.xlsx` as a ZIP/XML workbook, not a UTF-8 text file.
- Do not expose an unauthenticated synchronization endpoint.
- Do not generate order from `Item.query.all()` or another unordered result.
- Preview the proposed changes and preserve a rollback path before mutation.
- For large tables, use a staging table or set-based update instead of one
  commit per row.

## Completion criteria

- Source and actual inputs have unique stable IDs.
- Every intended record maps exactly once.
- Stored values match the chosen source semantics.
- API order is deterministic.
- Default frontend order matches the API.
- Automated comparison passes after the change.

## Resources

- Run [scripts/compare_order.py](scripts/compare_order.py) for deterministic,
  read-only comparison.
- Read [references/database-patterns.md](references/database-patterns.md) only
  when implementing database writes.
