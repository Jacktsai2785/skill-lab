# `collab review` evidence contract

## Input

`collab review` requires one or more repeatable `--evidence PATH` flags. Each path must be a
readable UTF-8 file of at most 1 MB. Use the original file whenever possible: a diff, a source
file, a Mermaid workflow, a log excerpt, or actual test output.

Supply a review objective with `--prompt`, plus one or more observable `--hard-ac` constraints.
Useful optional boundaries are `--non-goal`, `--hard-constraint`, and `--soft-constraint`.

## Execution model (synchronous, independent of `collab design`)

`collab review` does not run through the `Engine` that `collab design`/`collab run` use. It is
a single synchronous call: no `run_id`, no checkpoint/journal, no crash-resume, and none of
`collab status`/`collab calls`/`collab continue-run`/`collab resume`/`collab answer` apply to
it — those are design-run-only commands. The call blocks until every evidence pass has run its
reviewers and cross-platform verification, then writes the report and returns.

Each reviewer/verifier call is bounded by `--timeout-per-call-seconds` (default 600s, set by
`DEFAULT_ENGINEERING_REVIEW_TIMEOUT_SECONDS`). If any pass has a reviewer that times out or
errors, that reviewer is recorded in the top-level `rejected_reviewers` map, the report's
`status` field is `"incomplete"` (instead of `"completed"`), and the CLI prints `INCOMPLETE`
and exits non-zero — this is a deliberate fail-closed behavior so a partial (single-model)
result is never delivered looking like a complete dual-model review. Re-run the call (optionally
with a higher timeout) to get a complete result.

## Output

The command writes `<review_id>.json` under `<data_dir>/reports/` (default
`~/.collab-orchestrator/reports/`) and prints that path. There is no `collab report` re-render
for review — read the JSON file directly. Each finding carries the three-state fields:
`verification` (`confirmed`/`rejected`/`unverified`), `verified_by`, `verification_reason`,
`evidence` (`source_id`, `source_path`, `start_line`, `end_line`):

```json
{
  "verification": "confirmed",
  "verified_by": "codex",
  "verification_reason": "...",
  "evidence": {
    "source_id": "input-2",
    "source_path": "pre-push",
    "start_line": 29,
    "end_line": 30
  }
}
```

The top-level report also carries `status` (`completed`/`incomplete`), `passes`,
`timeout_per_call_seconds`, and `rejected_reviewers` (a map of `"pass-<n>:<reviewer>"` to a
failure reason, empty when `status` is `completed`).

`confirmed` means the supplied evidence supports the claim; `rejected` means it does not.
`unverified` is reserved for "could not be checked against the evidence at all" (a
tooling/citation failure) — findings are never left in an open "AI could not agree" state;
review has no human decision card. If `status` is `incomplete`, treat any findings in that
report as partial, not final.

## Size behaviour

The review pass cap is 512 KiB after source labels and headers are rendered. If a combined bundle
is too large, the CLI can split exactly one unified-diff-shaped source at `diff --git` file-section
boundaries. It does not split a single huge file section, arbitrary source files, or several large
sources. Split those deliberately before invoking review.
