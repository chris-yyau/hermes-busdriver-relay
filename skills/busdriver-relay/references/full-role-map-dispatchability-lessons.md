# Full role-map dispatchability lessons — PR #113

Use this note when making relay role-map entries first-class, changing `hermes-busdriver-status`, or responding to PR-grind/reviewer feedback about role routing.

**Current production status:** every role remains non-programmatic because no executable relay-role dispatcher exists. Adapter-shape proof is not production dispatch proof.

## Durable lessons

1. **Resolver-ready is not the same as dispatchable.** A role may be a first-class resolver role with a valid selected agent while still being unsafe for programmatic dispatch. For unverified adapter lanes, keep `status=resolved` / `ok=true` only as configuration evidence, but return `dispatch_allowed=false` and include explicit metadata such as `programmatic_dispatch_allowed=false`, `adapter_verified=false`, and `dispatch_blocker=<reason>`.
2. **OpenCode fallback/comparison roles stay non-dispatchable until the complete production safety proof exists.** If `relay.impl.secondary` or `relay.impl.fallback` select `opencode`, do not let `hermes-busdriver-relay-role` infer `dispatch_allowed=true` merely from a non-degraded `selected_agent` or adapter-shape proof. The current blocker is `agent_containment_and_credential_broker_unavailable`; keep `adapter_verified=false` and `programmatic_dispatch_allowed=false`. Only a future independently reviewed containment and credential-broker implementation may change both fields.
3. **Manual IDE roles are status/config evidence, not programmatic lanes.** `relay.ide.manual=cursor` should resolve cleanly but remain `programmatic_dispatch_allowed=false` / `dispatch_allowed=false` with `manual_ide_sidecar_not_programmatic`.
4. **Review-sensitive degradation should be separate from dispatchability.** `avoid_coding_agent_for_review=true` can degrade review/decision/backstop roles that select the current coding agent. Implementation/manual roles may intentionally match the coding agent; adapter dispatchability is a separate field and should not be encoded as `degraded` unless the config itself is invalid.
5. **Docs must avoid stale route contradictions.** Codex is implementation-primary metadata and PR lead, OpenCode + Go is secondary/fallback draft-only metadata, Pi is deferred history, Cursor is manual, and Claude Code/Busdriver is the sole canonical finalization authority. Every role remains non-dispatchable; same-provider Codex review also requires a fresh independent-session contract while `avoid_coding_agent_for_review=true`.
6. **Share role-map constants in tests.** Keep the 19-entry role inventory in a shared contract-test helper instead of duplicating it across status and role resolver tests; otherwise reviewer-fix rounds can update one test and leave another stale.
7. **PR-grind can keep old inline comments actionable after force-push.** If a reviewer comment is fixed but still appears as actionable on the latest head, inspect the review thread state. When the thread is genuinely addressed and not auto-resolved, resolve the review thread explicitly via GitHub GraphQL before rerunning PR-grind.
8. **After repo skill-source merges, check installed skill drift.** If the PR edits `skills/busdriver-relay/**`, compare the merged repo source with the installed Hermes skill copy. If they differ, run a separate installed-skill sync instead of declaring the live skill library fully updated.

## Verification checklist

- Focused tests for `test_status_probe.py`, `test_relay_role.py`, and `test_skill_references.py`.
- Full `tests/contract` suite.
- Resolver probes for at least `relay.impl.primary`, `relay.impl.secondary`, `relay.impl.fallback`, `relay.ide.manual`, `relay.pr.lead`, and `relay.pr.backstop`, checking `dispatch_allowed` and blocker metadata.
- PR-grind latest-head check after every fix push; do not merge until actionable comments are empty and required checks are clean.
- Clean-tree smoke before merge and clean-main smoke after merge when the repo has a smoke helper.
