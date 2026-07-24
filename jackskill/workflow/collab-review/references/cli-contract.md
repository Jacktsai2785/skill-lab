# `collab review` evidence contract

## Input

`collab review` requires one or more repeatable `--evidence PATH` flags. Each path must be a
readable UTF-8 file of at most 1 MB. Use the original file whenever possible: a diff, a source
file, a Mermaid workflow, a log excerpt, or actual test output.

Supply a review objective with `--prompt`, plus one or more observable `--hard-ac` constraints.
Useful optional boundaries are `--non-goal`, `--hard-constraint`, and `--soft-constraint`.

## Output

The command writes `review-<id>.json` under `~/.collab-orchestrator/reports/` (or `--data-dir`).
Each finding includes reviewer, verification state, verifier, claim, reason, and evidence:

```json
{
  "verification": "confirmed",
  "evidence": {
    "source_id": "input-2",
    "source_path": "pre-push",
    "start_line": 29,
    "end_line": 30
  }
}
```

`confirmed` means the supplied evidence supports the claim. `rejected` means it does not.
`unverified` means the verifier could not reliably confirm it; it is not a clean pass.

## Size behaviour

The review pass cap is 512 KiB after source labels and headers are rendered. If a combined bundle
is too large, the CLI can split exactly one unified-diff-shaped source at `diff --git` file-section
boundaries. It does not split a single huge file section, arbitrary source files, or several large
sources. Split those deliberately before invoking review.
