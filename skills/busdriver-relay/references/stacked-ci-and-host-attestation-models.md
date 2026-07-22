# Stacked CI and host-attestation models
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference before publishing or merging a bounded PR stack whose production trust model is tied to a specific OS, host, executable path, ownership mode, SIP/immutable flag, or reviewed byte digest.

## Busdriver's three verification planes

Do not collapse Busdriver delivery into a single CI job. The durable model has three distinct planes:

1. **Local authority plane:** the matching host runs repository gates, locks, litmus/pre-commit/pre-PR checks, executable ownership/SIP/digest attestation, diff-hash freshness, and trusted marker writers. These checks may depend on host facts that a generic runner cannot reproduce.
2. **Hosted portable plane:** GitHub Actions runs hermetic contract tests, static/security scanners, workflow checks, and other assertions that are genuinely portable. Keep production host anchors out of non-installed fixtures so this plane remains useful; do not degrade it to compile-only merely because production is host-frozen.
3. **Latest-head convergence plane:** PR-grind reads the live required checks, mergeability, reviews, comments/threads, and current PR HEAD, and combines those observations with fresh local authority evidence. PR-grind observes and adjudicates freshness; it does not execute host attestation or manufacture trusted markers.

A push or rebase invalidates convergence evidence even if both underlying planes were previously green. A self-hosted runner is an optional way to automate the first plane, not Busdriver's default authority model; never register a user's daily workstation without an explicit security decision.

CI topology also cannot overrule code review. Resolve or explicitly reject every material bounded-review finding before choosing among runner/attestation models. A green portable job, sealed local log, or runner migration does not convert an insecure or temporally broken capability slice into a mergeable one.

## Pre-publish compatibility gate

Local slice evidence and generic hosted CI answer different questions. Before fan-out, inspect and record:

- the supported production platform and exact host-attestation requirements;
- workflow runner OS/labels, interpreter, timeout, test command, and required check names;
- whether intermediate slices are temporal checkpoints or independently aggregate-suite-compatible;
- whether tracked manifests contain host-specific absolute paths, ownership/flag assertions, or executable digests;
- which tests actually spawn platform tools rather than merely asserting argv/constants, and whether those tests have an explicit platform marker, skip, fixture adapter, or matching runner;
- whether the final tree has actually run on the live hosted runner.

A workflow/implementation mismatch is a final-tree CI defect, not stale snapshot drift, when the only required job targets one OS while an unmarked test directly launches another OS's fixed binary (for example Ubuntu-only CI plus an unconditional `/usr/bin/sandbox-exec` behavioral test). A local pass on the supported host does not soften that classification. Either run the host-bound test on a matching attested lane, or keep a source-separated portable harness and name the hosted result honestly; do not silently skip the only behavioral proof and still call the generic lane production attestation.

Run a live CI canary before opening a large remote stack when local and hosted environments differ. If a workflow-dispatch or matching container is unavailable, use one bounded Draft canary rather than discovering the model mismatch after dozens of PRs exist. Draft visibility is useful, but do not merge until the execution model is explicit.

A local pass on the reviewed host does **not** imply that Ubuntu/macOS hosted runners can satisfy the same attestation. Record OS, runner identity, interpreter, tree OID, and evidence SHA with every claim.

## Temporal stacks and aggregate suites

A temporal slice is verified against its immediate base with the tests valid at that checkpoint. An aggregate final suite may legitimately depend on fixtures, schemas, inventories, or production bytes that land later. Therefore:

- do not run the final aggregate suite on every intermediate PR and interpret expected transition failures as candidate defects;
- do not weaken slice-local gates merely to make an aggregate workflow green;
- give hosted checks honest names that distinguish portable/static checks, slice-local checks, and host attestation;
- run the aggregate suite only where the final tree exists;
- bind every check/evidence record to the exact PR HEAD and immediate base; a push, rebase, or parent merge invalidates it.

If hosted CI cannot execute the exact slice-local command, choose and document an attestation model before merge rather than silently substituting another command.

## Three valid attestation models

### 1. Dedicated matching runner

Use an isolated runner with the same trust properties as production. Prefer a dedicated or ephemeral machine, same-repository branch gating, no fork execution, minimal credentials, and explicit teardown. Do not register a user's daily workstation as a self-hosted runner without an explicit security decision: workflow code would execute on that host.

### 2. Portable hosted CI plus sealed host evidence

Hosted CI runs syntax, diff, static security, and genuinely portable tests. A reviewed host runs the host-attestation and full platform-specific suite. PR-grind requires both sets of evidence and labels them separately.

This model is truthful for host-frozen software but has a trade-off: hosted CI does not independently reproduce the host-only assertion. Seal host evidence to tree/HEAD, command, interpreter, environment probe, logs, and SHA-256; never rename the portable job to imply that it ran the host suite.

### 3. Portability redesign

Refactor non-installed fixtures away from production trust anchors and explicitly mark the small set of true host-attestation tests. Generic CI then runs the portable suite, while a matching host still runs the attestation suite. This is the strongest long-term model when cross-platform CI matters, but it is a separate bounded engineering effort—not a quick CI edit.

Never add volatile hosted-runner executable digests to a production trust manifest merely to make CI green. Never fabricate a check run, use an admin bypass, or call a partial check the full suite.

## Test-harness boundary

Host-frozen production entrypoints must not expose an environment flag that disables trust validation. Portability belongs only in source-separated, non-installed test harnesses:

- inject system `git`/Python and fixture-only child executables after loading the production namespace;
- preserve production argv shape with test-only adapters when a platform tool (for example, a sandbox launcher) is absent;
- keep live network/GitHub helpers refusing by default in hermetic fixtures;
- retain separate tests proving production still dispatches only the frozen source;
- test every harness that loads production, including retained child harnesses, not just the top-level wrapper.

When diagnosing a large platform mismatch, first collect the full failure inventory and group by root cause. A bounded `--maxfail` run is useful for a first sample; use fixed, conservative worker counts for complete collection. `-n auto` can oversubscribe a small hosted runner and be slower than `-n 2` or `-n 4`.

Diagnostic workflow edits are not delivery evidence. Revert/squash them, restore reproducible dependency pins, and rerun the final gates on the intended HEAD.

## Required-check false positives

Secret scanners can flag credential-shaped comments and deliberate redaction fixtures. Classify every finding without printing the value. Remove detector-shaped comment examples or construct fixture payloads so no credential literal exists in source. Do not dismiss a required check merely because a finding is probably a fixture.

## Decision communication

When the attestation model needs user choice, first explain each option in plain language:

- what executes where;
- the main security benefit;
- the main cost or risk;
- which option is recommended and why.

Only then ask the user to select. Do not present several jargon-heavy choices without a short comparison.
