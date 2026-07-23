# Database synchronization patterns

Use the pattern matching the project's database and migration framework. The
examples are conceptual; adapt table and column names.

## Transaction pattern

1. Load normalized source values into a staging table.
2. Assert unique stable IDs and valid order values in staging.
3. Compare staging IDs with the target table.
4. Abort on unexpected missing or extra IDs unless policy allows them.
5. Update the target table by stable ID in one transaction.
6. Re-read and compare before commit when the framework supports it.

## PostgreSQL backfill with a CTE

```sql
WITH ranked AS (
  SELECT id, row_number() OVER (ORDER BY id) AS new_order
  FROM items
  WHERE display_order IS NULL
)
UPDATE items AS target
SET display_order = ranked.new_order
FROM ranked
WHERE target.id = ranked.id;
```

Use this only for a one-time fallback backfill when file-derived order is not
available. It does not synchronize an Excel SSOT.

## Deterministic API order

Always include a tie-breaker:

```sql
SELECT id, display_order
FROM items
ORDER BY display_order ASC, id ASC;
```

Add a uniqueness constraint only when duplicate order values are invalid for the
domain. Otherwise keep the stable tie-breaker.
