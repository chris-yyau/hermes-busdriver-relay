# Retiring an executor while preserving fail-closed evidence

Use this when a relay policy removes one production executor but keeps another, especially when historical adapter code is still valuable as contract evidence.

Current authority: `coding-workflow-authority-map-v0.1.md`. This procedural guide must not override that policy map.

Workflow entry point: start with this guide for policy, inventory, reseal, and postmerge convergence; use `executor-retirement-pr-grind-lessons.md` only for the closing review/delivery phase.

## Policy tuple first

Write one current-policy tuple before editing:

- the sole executor route;
- non-executor fallback/review metadata;
- production dispatch blocker;
- finalization authority;
- status of retired adapters: absent from production, historical/test-only, or deleted.

For the current relay policy: Pi is the sole executor route; Codex is fallback-coder/PR-lead metadata only; OpenCode is non-executor history; all relay dispatch/finalization authority remains false; the production dispatch blocker is fixed and no CLI flag or environment variable unlocks it.

## Retire all four surfaces

Removing a route is not complete until these surfaces converge:

1. **Runtime:** remove parser choices, route defaults, executable resolver branches, wrapper calls, smoke choices, and implementation-role assignments.
2. **Install/trust:** remove executable pins and production-entrypoint ownership. If old implementation code is still useful, move it from production-owned directories into `tests/fixtures/`; production must not import or call it.
3. **Declarations:** update authority maps, current status, README, ADRs, adapter docs, skill policy, and the current/historical document inventory. Historical files need a conspicuous non-production banner and current-authority pointer.
4. **Tests:** add a real production-entrypoint negative test proving the removed choice is parser-rejected before repo, credential, worker, or persistent-write access. Keep historical positive adapter tests explicitly fixture-only.

A permanently blocked compatibility choice is still a production choice. If policy says the executor is retired, reject it rather than retaining a blocked parser route.

## Structural-test deletion sweep

Moving or deleting one production executable changes more than path-specific tests. Before a full suite, search the contract suite for:

- basename/path allowlists;
- trusted-runtime and production-entrypoint inventories;
- AST/source discovery sets;
- redaction, subprocess-egress, root-owned-execution, durability, and write-loop derivations;
- minimum-count assertions that intentionally guard against vacuous discovery;
- docs-policy classification and active-policy unions.

Lower a discovery floor only when the exact removed production surface explains the decrement and the remaining expected members are still asserted. Do not merely make the number pass.

## Digest-closure reseal without churn

Trusted-runtime consumers form a digest graph. Reseal to a fixed point after runtime edits, but preserve source formatting:

1. recompute manifest digests from candidate bytes;
2. derive each consumer's expected pin value;
3. compare parsed current and expected values;
4. rewrite only assignments whose semantic value changed;
5. repeat until neither manifest nor consumers change;
6. run the independent manifest-closure contract.

Do not pretty-print every constant map unconditionally. That creates unrelated script churn, expands the digest graph, and obscures the policy diff.

## Efficient verification order

1. RED: production parser still accepts the retired executor.
2. GREEN: parser rejection plus no-side-effect assertions.
3. Focused runtime, manifest, dispatch-surface, docs-inventory, and skill-reference suites.
4. Run the full suite once with `-x` after a structural deletion to expose the first stale derivation cheaply.
5. Fix all same-class inventory/floor assumptions found by a repository-wide search.
6. Run the complete suite to completion.
7. Follow `executor-retirement-pr-grind-lessons.md` for candidate freeze, exact-diff hashing, immutable review, and latest-head PR-grind mechanics. Start that sequence only after steps 1–6 pass.
8. After merge, converge live relay config and the installed skill copy, then verify clean main and the retired executor's absence from production surfaces.

## Pitfalls

- A move into `tests/fixtures/` must update fixture loaders and historical contract tests, while production scanners must stop enumerating that file.
- Do not classify a historical adapter README as current policy merely because current docs link to it; classify it as historical and banner it.
- Test-only executable bits need an explicit reason. Prefer invocation through the test interpreter when direct executability is unnecessary.
- Do not begin PR grind or immutable review while broad tests are still discovering structural fallout.
