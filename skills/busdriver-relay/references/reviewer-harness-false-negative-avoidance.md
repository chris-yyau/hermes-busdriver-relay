# Reviewer harness false-negative avoidance
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this note for exact-boundary closing reviews that run several focused pytest groups, deterministic boolean probes, and a postflight inventory before END.

## Pytest selection discipline

Do not combine unrelated test files and several `-k` expressions in one pytest invocation. Pytest applies the final effective `-k` expression to the whole collection, which can silently select only a small subset while still returning rc=0.

Preferred patterns:

1. Run each focused group as a separate pytest process with its own external `--basetemp`.
2. Append every group to one external evidence log.
3. Capture each process rc and fail the aggregate if any group fails.
4. Record per-group passed/deselected counts; reconcile them against the intended matrix before accepting the run.

A successful but unexpectedly small count is a reviewer-harness problem, not positive candidate evidence. Fix only the harness and rerun the intended groups.

## Boolean probe aggregation

For probes containing negative assertions, never use `all(result.values())` unless every field is expected to be true. Fields such as `replacement_executed=false`, `dispatch_attempted=false`, or `sentinel_exists=false` represent success when false.

Compute the final `ok` value from explicit predicates:

- required-positive fields are true;
- required-negative fields are false;
- every mutation both fails closed and records zero dispatch;
- normal and exceptional cleanup assertions are true.

Keep the first malformed aggregate as an operational note, not a candidate finding, when the underlying observations were correct. Rerun after fixing only the external aggregator.

## Candidate postflight inventory scope

A verifier-rebuilt candidate may be a functioning Git worktree and therefore contain `.git` metadata that is intentionally outside the authenticated source-entry inventory. A naive recursive walk will report hundreds of false extras.

For an independent postflight:

1. Derive inventory scope from authenticated START/boundary entries.
2. Exclude `.git` metadata unless the boundary explicitly includes it.
3. Compare path, type, exact mode, size, and content digest for every authenticated entry.
4. Detect extra non-metadata files and cache/bytecode residue separately.
5. Recompute the canonical entry digest using the boundary's serialization; for the current v1 boundary shape this is compact, sorted-key JSON over the ordered entry list.
6. Require count, per-entry comparison, and canonical digest to agree before END.

If the initial walk included `.git`, correct the external inventory scope and rerun. Do not delete candidate Git metadata to force a match.

## Closing interpretation

Harness mistakes that do not alter the candidate are operational notes. They become `INCOMPLETE` only if they prevent a valid rerun, draft freeze, END, report, or sidecar. They are not candidate findings when corrected before END and the valid rerun supplies complete evidence.
