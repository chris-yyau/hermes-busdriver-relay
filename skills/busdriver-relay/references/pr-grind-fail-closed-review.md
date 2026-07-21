> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Busdriver relay PR-grind fail-closed review lessons

Use for Hermes Busdriver Relay PR/delivery work that touches status envelopes, finalization-readiness, litmus/pre-PR marker evidence, or helper subprocess wrappers.

## Review policy

- Treat medium correctness or data-egress findings from Codex lead/backstop as fix-before-PR for relay control-plane work, even when the mechanical PR-mode gate only blocks `high` findings.
- Any commit/amend that changes `base...HEAD` invalidates prior review artifacts bound to the diff hash. Re-run Codex lead, recompute `REVIEWED_DIFF_HASH`, rerun backstop, then write trusted backstop verdict/PR marker.
- Do not hand-write marker artifacts. Use the trusted `run-review-loop.sh --write-backstop-verdict` and `--write-pr-marker` path only after both voices are fresh and pass.

## Status-envelope fail-closed rules

When integrating nested helper output (for example litmus/pre-PR status) into delivery/finalization evidence:

1. Validate schema exactly before trusting nested fields.
2. Validate `read_only is True`.
3. Validate authority flags are explicitly false, including `finalization`, `commit`, `push`, `pr`, `merge`, `deploy`, `release`, `publish`, and `marker_write`.
4. Validate boolean fields by type (`isinstance(value, bool)`), not truthiness (`bool(value)`).
5. Validate status enums. Unknown status values with `ok=true` must fail closed (for litmus status use `litmus_status_schema_invalid` or the existing schema/malformed reason) and block delivery/readiness.
6. Treat helper subprocess nonzero as fail-closed even when stdout contains parseable JSON.
7. Keep final decision authority false even for ready/handoff statuses.

## Data-egress rules

- Never copy raw helper stdout/stderr, marker payloads, warnings, blockers, repo maps, or state-dir maps into user-visible status envelopes.
- Whitelist summary fields. For litmus summaries, the safe shape is repo/state metadata, known marker names, sanitized marker metadata, recognized decision status, false authority flags, and empty/sanitized warnings/blockers.
- Redact before tail-bounding stdout/stderr; otherwise a secret can be truncated into a form that bypasses redaction.
- Add sentinel tests for both parse-error and valid-JSON/nonzero paths: custom helper emits a fake secret in stdout/stderr; final JSON must not contain the sentinel while still reporting the correct fail-closed reason.

## TDD/gate loop

- Add focused RED tests for every reported gap, then production fix, then focused suites, full `uvx --from pytest pytest tests/contract -q`, smoke, `git diff --check`, and static secret scan.
- After fixes, amend the feature commit before re-running PR-mode review so the review diff matches the intended PR.
