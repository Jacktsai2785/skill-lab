# `collab review` evidence contract

## Input

`collab review` requires one or more repeatable `--evidence PATH` flags. Each path must be a
readable UTF-8 file of at most 1 MB. Use the original file whenever possible: a diff, a source
file, a Mermaid workflow, a log excerpt, or actual test output.

Supply a review objective with `--prompt`, plus one or more observable `--hard-ac` constraints.
Useful optional boundaries are `--non-goal`, `--hard-constraint`, and `--soft-constraint`.

## Execution model (v4.2 collector journal)

`collab review` now runs through the same `Engine` as `collab design`: it prints `run <run_id>
started`, then advances through its own review states
(`review_cross_reviewing` → `review_rebuttal` → `review_judge_lite` → `review_completed`,
or `awaiting_user_decision` if it needs a human call) until it converges or blocks. Every
model call is journaled (checkpoint + idempotency key), so an interrupted review resumes
instead of re-running and re-billing everything:

```bash
collab status <run_id> --data-dir ~/.collab-orchestrator
collab calls <run_id> --data-dir ~/.collab-orchestrator      # per-call journal status
collab continue-run <run_id>                                  # advance a still-runnable review
collab resume <run_id>                                        # resume from a paused_* state
collab ui                                                      # dashboard view of the run
```

A verifier "rejected" verdict is no longer written straight to the report as a disagreement.
The finding's original author gets one bounded rebuttal; if it still stands, two fresh judges
(one per platform) each issue a binary verdict (`confirmed_dominates` / `rejected_dominates` /
`insufficient_evidence`). They must independently agree AND each ground their verdict in a
real, locatable evidence quote for it to be adopted — the same agree-or-no-dominance rule
`collab design`'s JUDGING state uses, just binary instead of open-ended. Only a genuine
no-dominance disagreement between the two judges creates a decision card:

```bash
collab answer <run_id> <card_id> --choice confirmed   # or rejected
```

## Output

The command writes `<run_id>.json` under `~/.collab-orchestrator/reports/` (or `--data-dir`),
and `collab report <run_id> --format json` re-renders the same report later (md/html are the
`collab design` report shape and are not supported for a review run). Each finding still
carries exactly the same three-state fields as before — `verification`
(`confirmed`/`rejected`/`unverified`), `verified_by`, `verification_reason`, `evidence` — plus
one new, additive field:

```json
{
  "verification": "confirmed",
  "verified_by": "codex",
  "verification_reason": "judge-lite dual agreement (confirmed_dominates): ...",
  "evidence": {
    "source_id": "input-2",
    "source_path": "pre-push",
    "start_line": 29,
    "end_line": 30
  },
  "convergence": {
    "disputed": true,
    "rebuttal": {"stands": true, "reason": "...", "evidence_source_id": "input-2",
                 "evidence_quote": "..."},
    "judge_lite": {"outcome": "adopt", "disposition": "confirmed_dominates",
                   "judges": {"claude": {"disposition": "confirmed_dominates", "reason": "..."},
                              "codex": {"disposition": "confirmed_dominates", "reason": "..."}}},
    "user_decision": null
  }
}
```

The top-level report also gains `convergence_summary` (counts of disputed / conceded-on-rebuttal
/ resolved-by-judge-lite / escalated-to-user findings).

`confirmed` means the supplied evidence supports the claim — either because verification agreed
outright, or because rebuttal + judge-lite (or a user decision after no-dominance) resolved a
dispute in its favor. `rejected` means the opposite. `unverified` is reserved for "could not be
checked against the evidence at all" (a tooling/citation failure) — it is never used for "the AI
argued and could not agree"; that case is `awaiting_user_decision` + a decision card instead, and
only becomes `confirmed`/`rejected` once answered.

## Size behaviour

The review pass cap is 512 KiB after source labels and headers are rendered. If a combined bundle
is too large, the CLI can split exactly one unified-diff-shaped source at `diff --git` file-section
boundaries. It does not split a single huge file section, arbitrary source files, or several large
sources. Split those deliberately before invoking review.
