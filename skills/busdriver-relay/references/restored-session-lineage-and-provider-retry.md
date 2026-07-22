# Restored-session lineage reconciliation and safe retry

Use this when a long Busdriver relay resumes after context compaction, process-notification delay, provider interruption, or another session may have advanced the repo.

## 1. Treat summaries as navigation, not current state

- Never resume a numbered candidate solely from a compacted summary.
- Read durable source and artifact state first: current Git status/HEAD, running mutators, boundary files, review lanes, result JSON, and logs.
- Enumerate all existing candidate numbers before creating a new one. A restored session may have advanced many generations beyond the summary.
- For every immutable boundary, recompute current file digests against its entry inventory. The newest *matching* boundary is authoritative; the numerically newest boundary may already be stale.
- Never overwrite an existing candidate, boundary, lane, or runtime directory. If no boundary matches current source, use the next unused generation only after gates pass.

## 2. Reconcile post-freeze drift before acting

If files changed after the last matching boundary:

1. Identify exact mismatches and modification times.
2. Check for active source mutators and whether their open files/cwd touch the repo.
3. Observe source digests briefly to ensure they are stable.
4. Do not kill unrelated resident model/MCP processes merely because their names match a reviewer.
5. If the drift is intended and stable, treat the whole current tree as a new combined candidate and rerun targeted tests, full inventory/partitions, fixed point, hygiene, boundary, and reviews. Never transplant old reviews.

## 3. Delayed background notifications are hints only

- A completion notification, `exit None`, or a restored pending tool result is not closure.
- Read the lane/partition's durable `result.json`, report, checksum, and log tail; verify expected counts and exit status.
- Check process state before retrying. If the original process is still active, wait. If durable success already exists, do not launch a duplicate retry.
- When notification and durable evidence disagree, durable authenticated artifacts win.

## 4. Review-lane validity

A lane is complete only when all are true:

- START closure authenticates the intended immutable source digest.
- Candidate and immutable review-view closures match that digest.
- The report is non-empty, substantive, from the assigned native reviewer, and has the required verdict token.
- END closure matches START and proves no snapshot drift.

END success never upgrades a missing, generic, authentication-only, or zero-byte report into a review.

**User-specific authority rule:** never use Agy/Antigravity as a Claude review lane. Claude authority must come from the native approved Claude route. A fallback may be used only in a role the Busdriver policy permits; do not relabel another provider as Claude.

## 5. Provider safety-filter retry

When a legitimate defensive review or delivery request is blocked by a provider safety filter:

1. Automatically retry once with narrower scope, explicit authorized/defensive context, and removal of unnecessary exploit detail.
2. If configured and policy-compatible, retry through an approved fallback provider without changing the claimed reviewer identity.
3. Stop immediately after success.
4. If safe retries still fail, preserve the blocker and report it; do not repeatedly rephrase prohibited content or attempt to bypass safety controls.

## 6. Verification checklist before claiming continuation

- [ ] Current source is stable and no active mutator owns it.
- [ ] Existing candidate lineage has been enumerated.
- [ ] A matching boundary was found, or all gates were rerun for a new generation.
- [ ] Partition totals reconcile with collected inventory.
- [ ] Fixed point made no unaccounted source change.
- [ ] Hygiene has no staged/index or cache residue.
- [ ] Every assigned native reviewer has valid START/report/END evidence.
- [ ] Any post-review source change creates a new candidate and invalidates prior reviews.
