# Capability-sliced ADR/docs/skill/config manifest lessons

Use this when rescuing or stacking a large dirty Busdriver-relay worktree whose ADRs, docs, skill source, and config must follow production behavior rather than lead it.

## Read-only intake

1. Diff the working tree against the PR base, not only `HEAD` or the index.
2. Enumerate both tracked changes and untracked files under every requested root. Ordinary `git diff` omits untracked config/reference files.
3. Record per-path `numstat`, hunk counts, and hunk headers. Re-run with end-of-line whitespace ignored to distinguish substantive edits from banner-only or EOL-only synchronization.
4. Count the complete target set once: full-path assignments plus synthetic hunk/line-range assignments for mixed files. Every retained path and every mixed hunk must have exactly one owner.

## Classify by behavior dependency

Prefer a small vocabulary of capability owners, for example:

- runtime trust / authenticated executable closure;
- untrusted Git observation and lock hardening;
- agent/verifier containment and adapter dispatch policy;
- delivery/finalization executor and operation-specific blockers;
- docs-only historical classification, inventory, and final evidence refresh.

A documentation edit belongs with the behavior whose truth it reports. Do not merge production-claiming docs before the implementing/default-deny behavior and tests exist.

## Mixed-document splitting

Hunk-split broad status and skill files instead of assigning the whole path to whichever slice is largest. Typical mixed files include `CURRENT_STATUS.md`, settling-check docs, the umbrella `SKILL.md`, and combined ADRs.

- Assign separable hunks by hunk header.
- For a newly added file represented as one Git hunk, use explicit new-file line ranges as synthetic sub-hunks.
- If one changed line contains several capabilities and cannot be meaningfully split without rewriting, assign the whole line to a final convergence slice and declare all prerequisite capabilities.
- Split historical/superseded banners away from substantive semantic edits in the same reference.

## Config dependency traps

### Trusted runtime manifests

A digest manifest is behavior/config, not documentation. It couples every authenticated executable, plugin byte, embedded consumer pin, and production entrypoint it names. Land it only after the covered bytes are stable, or regenerate it in every stacked layer that changes covered bytes. Never reuse final-tree digests in an earlier slice.

### Documentation policy inventories

A doc-policy inventory is docs-only control data, but it depends on the final retained path set and may reference root docs owned by another slice. Land it after all classified docs exist and after cross-owner README/agent-guidance changes are settled.

Treat test collection as a real dependency edge: if a documentation-contract test reads the inventory at module import/collection time, the inventory must already exist in that slice's base or land in the same slice before the test. If the final inventory would describe docs that are not yet present, either defer that test to the convergence slice or stage a valid intermediate inventory. Never add a collector that requires final policy data before the policy data itself.

## Slice sizing and order

Keep each docs slice comfortably below the review ceiling (normally about 1,000 changed lines). Use conservative budgets rather than packing to the limit. A robust order is:

1. production behavior slices;
2. trusted-runtime/config freeze;
3. capability-specific docs (agent/runtime, then delivery/finalization);
4. historical banners and policy inventory;
5. final `CURRENT_STATUS` verification/review evidence on one immutable boundary.

Exact review evidence is last-mile documentation. If the text itself says the repair line is not frozen or review is incomplete, do not carry it forward as final status; refresh it after the final boundary and reviews.

## Mechanical production-test pairing

Do not infer test ownership from directory names alone. Derive pairings from the current tree:

1. search test sources for each production path and basename;
2. parse test modules and record the production constants, fixture constants, and shared helper imports they bind;
3. map changed test hunks to their enclosing `test_*` functions;
4. map changed production hunks to enclosing top-level functions/classes;
5. add parity suites that dynamically enumerate multiple production copies as cross-slice closure dependencies, not as the sole direct test for one file.

Report the result as `production path/function ↔ direct test file/function ↔ fixture/parity suite`. Shared fixtures must name every consumer. A basename hit is evidence to inspect, not proof by itself; generic README or schema names can produce false positives.

## Budget lower bounds and copied primitives

Before proposing a stack, compute changed-line totals as additions plus deletions, counting every untracked line as an addition. State the hard lower bounds:

```text
minimum PRs by production = ceil(production_changed_lines / production_budget)
minimum PRs by total      = ceil(total_changed_lines / total_budget)
```

This prevents presenting seven capability groups as seven PRs when the byte budget already requires fourteen or more.

Cross-cutting copied primitives need special treatment. If an identical bounded-subprocess/trusted-source/write primitive is pasted into many entrypoints, derive the exact consumer set and line cost from AST/function spans. Split the consumers into budget-safe foundation layers, then land the enumerating parity test only after all required copies are present. If atomic parity cannot fit the budget, prefer a reviewed shared module; otherwise declare the staged temporary gap explicitly. Never hide several thousand copied production lines inside unrelated vertical slices.

## Closure checks for stale allowlists and pins

Static policy tests often contain fingerprint maps, dispatch exemptions, sanitizer approvals, or forwarded-argument allowlists. After production functions are deleted or renamed, programmatically verify that every `(file, symbol)` key still resolves to a live installed symbol. A test can remain green while a stale exemption silently survives if it validates only discovered call sites.

Likewise, verify manifest sections separately:

- repo-local production/adapter/runtime hashes;
- embedded consumer pins and their dependency direction;
- external executable availability and digest.

An unavailable external executable is current environment state, not a permanent skill rule. Report its present fail-closed consequence, but preserve only the verification method here.

## Verification

- Recount assigned paths and untracked paths after classification.
- Verify every target path appears exactly once and every declared mixed hunk has one owner.
- Check each proposed slice's changed-line budget programmatically and state both lower bounds.
- Confirm every production-test-fixture pairing and every shared parity dependency.
- Validate fingerprint/dispatch allowlists against live symbols so removed functions leave no stale exemption.
- Validate repo-local manifest hashes; separately report external-runtime availability.
- Run `git diff --check` read-only.
- For an analysis-only request, do not run potentially mutating tests or write a manifest/rescue file unless the user explicitly permits it; return the proposed ownership manifest in the report.