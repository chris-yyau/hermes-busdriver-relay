# Production documentation / ADR / skill consistency audit

Use this for read-only audits that compare relay documentation, ADRs, status pages, and the repo skill against current production adapter behavior.

## Audit order

1. Establish the production capability facts first: accepted `--agent` choices, smoke-supported agents, default executable resolution/integrity policy, successful real-smoke outcomes, and authority flags.
2. Audit active surfaces together: root README, `docs/CURRENT_STATUS.md`, all ADR status/amendment sections, repo `SKILL.md`, authority maps, and current-policy references.
3. Search for stale route vocabulary broadly: removed agents, `custom`, legacy Codex implementation exceptions, OpenCode `candidate`/`pending proof`/`non-programmatic` wording, obsolete smoke claims, and completed proof work still listed as roadmap work.
4. Separate historical records from current policy. Preserve old PR/session facts, but add a clear superseded/historical note where copyable commands or policy statements no longer match production.
5. Validate local links from `SKILL.md` to `references/*.md`; missing session references are actionable documentation drift.
6. End with exact file/section recommendations only, grouped as blocking/nonblocking. Do not edit during a read-only audit.

## Canonical capability distinctions

Never collapse these into a single implemented/blocked label:

- **Dual review:** read-only freshness/readiness evidence may be implemented while programmatic dual-review execution remains policy-blocked.
- **Trusted markers:** invoking a Busdriver-owned trusted writer seam may be implemented while raw Hermes marker creation, update, deletion, consumption-as-authority, and generic interop remain policy-blocked.
- **PR grind:** read-only check/poll/status wrappers may be implemented while an autonomous mutating fix/push/re-poll loop remains policy-blocked.
- **Delivery operations:** distinguish an implemented CLI/gating surface from a side effect that is still fail-closed because a required runtime precondition is unavailable.

## Policy migrations are cross-surface contracts

A routing/default policy change is not a docs-only replacement. First derive the active graph from the checkout; do not trust a stale handoff, search-hit count, or assumed manifest/inventory schema. Parse the actual policy inventory and trust manifest, then classify each hit as active runtime, active contract pin, current documentation, historical/superseded provenance, or generated digest.

Drive the migration with a focused RED test, then audit and update together:

- status/default route constants and the shared role-map fixture;
- metadata-only planners (`selected_agent`, `current_agent`, and every no-call/authority-false field);
- production parser defaults and help text;
- resolver consumers such as delivery-status/readiness, not only the resolver itself;
- trusted-runtime manifest rows and every embedded digest consumer;
- current README/status/authority map/ADR/repo-skill wording;
- live relay config and the installed umbrella skill as separate post-merge operational consumers.

Keep these distinctions explicit:

- **Preference is metadata, not execution.** If the new primary has no production adapter, do not add an agent token, wrapper, dependency, or executable pin merely to make the prose symmetric. Keep production dispatch false with a precise blocker.
- **Resolved is not dispatchable.** A read-only resolver may return `status=resolved` / `ok=true` with `dispatch_allowed=false`. Downstream status consumers should accept that as valid configuration evidence while preserving false authority; add negative tests that reject root or nested dispatch/mutation/finalization values that become true.
- **Fixed-blocked parsers need no implicit worker.** Use `noop` or require explicit selection, while retaining explicit historical harness choices. Never turn a metadata-primary agent into an executable route as a side effect of convergence.
- **Delivery Mode is separate from agent dispatch.** Do not disable or relabel an explicitly gated operator operation merely because all reusable agent-dispatch flags are false.
- **Reviewer independence outranks a tidy default map.** If the new implementation primary is also selected for review-sensitive roles, let those roles degrade or obtain an explicit replacement route; never weaken `avoid_coding_agent_for_review` to make tests green.

Build digest refresh order from actual embedded consumers: changed leaf helper → direct parent pins → readiness/smoke aggregators → top-level dispatcher → manifest. Do not assume a top-level package-tree field exists, and do not remove retained adapter/executable pins while blocked compatibility code still reaches those bytes. Manifest self-consistency tests and live executable attestation are separate checks; an environment reseal is a separately reviewed runtime change, not policy-convergence cleanup.

Do not overwrite an installed umbrella skill wholesale from a smaller repo copy: installed skills may contain additional durable references. Patch active policy sections and leave clearly labeled historical/superseded references intact. Historical commands, adapter proofs, and PR narratives may stay when unmistakably bannered; remove only claims that they are current/default/preferred. Likewise, report the latest sealed `main` authority separately from an unsealed follow-up candidate so the status page does not claim new bytes were covered by old evidence.

For immutable audits, route pytest temp/cache/bytecode outside the checkout and disable pytest's cache provider. Run targeted policy tests before broad suites. Do not let `set -e`, a failed broad suite, or a tool budget consume the mandatory final `HEAD`/branch/status/diff recheck; capture failures, continue to focused diagnostics, and always close the checkout boundary before reporting.

## Production pin reporting

Machine-specific executable paths and SHA-256 pins are verification evidence, not timeless policy. Record exact observed values in `CURRENT_STATUS` (or a verification artifact), and let README/SKILL describe the fail-closed pinning rule symbolically. Never copy a user-specific path into durable generic policy without labeling it as current observed production evidence.

## Common drift patterns

- README or SKILL advertises an agent choice rejected by production argparse.
- `agent-smoke` docs omit a newly supported real adapter or retain removed legacy smoke routes.
- ADR status says “current status has no dispatcher/executor” after a later ADR implemented a narrow executor.
- A later ADR lists remaining blocked surfaces but omits one still-blocked contract such as programmatic dual review.
- Current-policy references retain pre-proof wording after an adapter was promoted.
- A roadmap/count reference still treats `implemented_gated` rows as `policy_blocked`.
- Top-level docs call an operation a real side-effect executor while its authoritative ADR says it always fails closed on an unavailable precondition.

## Reporting template

For each finding include:

- priority: blocking or nonblocking;
- exact file and section/line range;
- the stale claim;
- the canonical replacement wording or state transition;
- whether the text should be updated, marked historical/superseded, or linked to current verification evidence.
