# Relay router role policy — July 2026

Session outcome: the user refined Hermes/Busdriver relay role assignment after comparing Pi, OpenCode+Go, Codex, Claude Code, Grok, Gemini, Cursor, and UltraOracle. This is a durable policy note for future relay-router/status/config work.

## Core split

- **Busdriver + Claude Code** remain canonical authority for workflow, gates, reviews, litmus/pre-PR/PR-grind semantics, commits, PRs, merges, and finalization.
- **Hermes** remains GPT-based relay/router/status/finalization-support. It should expose route/status/handoff envelopes and coordinate draft/review lanes, not become a second Busdriver.
- **Pi** is the confirmed primary Busdriver-compatible tool-harness / adapter candidate. Keep it as target-state until schema, wrapper, smoke, and contract tests pass; it is not Busdriver authority.
- **Codex** is the current primary implementation draft worker.
- **OpenCode** is a generic/opencode-go experiment or future comparison lane unless a Busdriver-compatible adapter/plugin is rebuilt and verified. It is not the selected tool-harness direction now that Pi is confirmed.

## Relay role map

### Blueprint

The user corrected that blueprint has three reviewers plus an arbiter. Do **not** say “blueprint = Claude Code” as a whole.

Preferred relay blueprint assignment:

```text
relay.blueprint.reviewer_1 = agy
relay.blueprint.reviewer_2 = claude-code   # replaces the old Codex slot
relay.blueprint.reviewer_3 = grok
relay.blueprint.arbiter    = fresh-codex
```

Rationale: preserve Agy/Grok reviewer diversity, use Claude Code for the slot that should avoid Hermes-main GPT/Codex echo chamber, and use a fresh Codex arbiter/session for convergence rather than the implementation session.

### Council

Preferred relay council assignment:

```text
relay.council.architect  = inline          # Hermes main GPT synthesis/architecture
relay.council.skeptic    = claude-code
relay.council.critic     = fresh-codex
relay.council.pragmatist = agy             # keep existing role
relay.council.researcher = grok            # keep existing role
```

Do not replace the existing Agy/Grok council roles when introducing Claude Code / fresh Codex lanes.

### Litmus and PR mode

User explicitly decided litmus stays Codex without extra independence/backstop caveats:

```text
relay.litmus.reviewer = codex
```

PR mode:

```text
relay.pr.lead     = fresh-codex
relay.pr.backstop = claude-code
```

PR lead should be a fresh Codex session, not the same implementation context.

### Implementation

```text
implementation.primary.current            = codex
tool_harness.primary_candidate            = pi
implementation.secondary.future_candidate = opencode only after adapter/smoke/tests; otherwise generic lane only
```

The user has confirmed Pi for the tool-harness direction. Do not promote Grok/Cursor Composer into the formal implementation lane unless the user changes this policy later, and do not present OpenCode as Busdriver-compatible unless its adapter/plugin is restored and verified.

## UltraOracle placement

UltraOracle is present in Busdriver as an optional GPT-5.5 Pro expert-witness surface. Treat it as an explicit escalation / expert witness, not a normal reviewer, council vote, litmus reviewer, PR backstop, or arbiter.

Preferred placement:

```text
relay.expert_witness.ultraoracle = optional escalation
```

Use it for high-impact architecture/workflow decisions, reviewer disagreement, upstream adoption/sync questions, or explicit user requests. Render separately from normal voices.

Review labels matter:

- `ORACLE_SUMMARY_REVIEW` — saw only prompt/summary/design text; weak advisory only.
- `ORACLE_REPO_ATTACHED_REVIEW` — saw attached raw repo evidence.
- `ORACLE_RETRIEVAL_REVIEW` — two-round retrieval loop; strongest form.
- `ORACLE_FAILED` — attempted but unusable; not evidence.

Even strong UltraOracle output remains advisory/expert-witness evidence that must be validated by the Busdriver/Fable/arbiter path before becoming load-bearing gate evidence.

## Config/status implementation guidance

When implementing this policy in relay config/status helpers:

- Put relay-owned role config under `~/.hermes/busdriver-relay/config.json`, not `~/.claude/busdriver.json`.
- Preserve `not_busdriver_native_claude_runtime: true` for Hermes-side role evidence unless the invocation genuinely runs inside Busdriver/Claude native workflow.
- Expose mode metadata such as `inline`, `fresh`, `read_only`, `mutating_draft`, `candidate`, or `expert_witness` rather than using bare agent names only.
- Keep all finalization/commit/push/PR/merge/marker-write flags false for relay role status.
- If Hermes invokes Claude Code directly as a relay reviewer/backstop, label it Hermes-side evidence, not Busdriver-native gate approval.
