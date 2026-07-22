# Frozen state-integrity and policy-ordering review patterns

Related frozen-review detail remains in:

- `operation-dispatchability-doc-consistency.md`
- `frozen-security-review-blocker-tdd.md`
- `production-fail-closed-seams-and-freeze-provenance.md`
- `frozen-tests-docs-integrity-review.md`
- `frozen-correctness-state-integrity-review.md`
- `frozen-correctness-negative-probe-patterns.md`

Use this reference when a frozen Busdriver/Hermes relay candidate contains permission metadata, production policy blockers, credential-capable helpers, or ownership locks.

## 1. Treat producer omissions as authority bugs

A strict consumer cannot detect a field that the producer silently filled with a permissive default. For permission/proof metadata:

- every default role must explicitly declare boolean permission and proof fields;
- never use permissive fallbacks such as `metadata.get("allowed", True)`;
- missing or wrong-typed fields must emit explicit false values, degraded state, and a stable blocker;
- mutation tests must remove **each** required field independently and test wrong types, not only inspect the healthy default map;
- test both the producer envelope and the final dispatcher-facing consumer.

Fail-closed output should preserve enough diagnostics to identify metadata invalidity even if a separate config error also exists.

## 2. Put policy blockers before credential-capable discovery

A production-negative operation must return its policy blocker before any helper that could inspect a repo, PR, GitHub config, credentials, or launchable command.

Verification pattern:

1. Unit test: replace the first credential-capable helper with a sentinel that raises if called.
2. Invoke the real production entry point with realistic arguments such as a PR number and caller verifier.
3. Assert the sentinel was never reached, `delivery_status`/worker output is absent, authority flags remain false, and no run artifact implies execution.
4. Assert the steps envelope begins with the policy-blocked operation; it must not fall through to generic `plan_only` or advertise a pending helper that intentionally never ran.
5. Direct probe: in a fresh HOME, make the credential file a FIFO and strip ambient token variables. The blocked command must return quickly without opening or altering the FIFO.

The direct FIFO probe complements—not replaces—the unit sentinel.

## 3. Release ownership with compare-retire, not check-then-rmtree

`read token -> rmtree(canonical path)` is a TOCTOU bug: a non-cooperative replacement can occupy the pathname between the check and deletion. An advisory lock protects only cooperating callers.

Safer release discipline:

- require the original token; expose no unrestricted `--force` bypass;
- atomically rename the canonical generation to a unique quarantine/retirement pathname;
- re-read and validate the moved lock ID and token;
- on mismatch, restore the moved replacement when canonical is free, otherwise preserve it at quarantine and return blocked;
- never recursively delete a pathname merely because an earlier read matched;
- if the platform lacks a true atomic compare-delete primitive, retaining a non-active tombstone is safer than pretending pathname deletion is CAS.

Required race tests:

- replacement installed immediately before the rename is not deleted;
- a second owner appearing before restoration leaves both generations preserved;
- wrong token fails;
- `--force` is rejected by the CLI parser;
- successful release makes the canonical lock inactive and reports the retired generation identity.

Retained tombstones create storage and metadata-retention obligations. Document their non-active status and define an explicit, separately reviewed retention/GC policy rather than hiding cleanup inside ownership release.

## 4. Freeze every repaired generation independently

When a frozen review finds a blocker:

1. Mark that exact digest `BLOCKED`; never edit its frozen bytes.
2. Clone a new working generation from the verified candidate/source lineage.
3. Add a RED regression, implement the minimal fix, run targeted GREEN tests, then run the complete isolated-HOME suite.
4. Rebuild deterministic patch, source-record tar, manifest, and candidate tree.
5. Pin the verifier to manifest digest, patch/tar digests, candidate tree, base HEAD, origin/base, branch, and record counts.
6. Rebuild a candidate from the artifacts and run the complete suite there with an explicitly printed internal return code.
7. Run start and end/final frozen verifiers. Missing end verification means `BLOCKED`, even if tests passed.
8. Dispatch independent correctness, trust-boundary, and tests/docs lanes against the rebuilt candidate only.

Keep source tests, rebuilt-candidate tests, and artifact-integrity verification as distinct evidence.

## 5. Active documentation needs negative contracts

Presence of a blocker token is insufficient if the same active surface also claims the capability is enabled. Scan all operator-visible and agent-visible surfaces together:

- README and CURRENT_STATUS;
- the active skill, its authority maps, and every linked reference that gives operational instructions;
- adapter READMEs;
- accepted ADRs, especially older ADRs that still describe a former production posture;
- executable module docstrings and `--help` text, including smoke helpers.

Do not assume an ADR or “lessons” reference is historical merely because it is old. If it remains accepted, linked by the active skill, or written in imperative/current-tense language, treat it as active policy. A script whose implementation now fails closed is still inconsistent if its docstring/help says it launches a real worker, runs a caller verifier, or produces a successful draft.

Contracts should reject stale positive phrases and require:

- production versus non-installed harness separation;
- blocker ordering where security depends on it;
- parser exposure is not dispatchability;
- historical successful smoke is provenance, not current containment proof;
- lock release semantics match the implementation (token-only, replacement-preserving, no unsafe pathname deletion);
- accepted ADRs and linked references either match current production behavior or carry an unmistakable superseded/test-harness-only banner;
- script docstrings/help describe the expected blocked result when the production command is intentionally non-dispatchable.

A focused docs test that checks only newly edited files is not enough. Add a repository-wide policy-claim test over the complete active-surface inventory, and maintain an explicit allowlist only for clearly bannered historical quotations.

## 6. Audit the trusted-runtime manifest as an ownership map, not only a hash list

A test that compares manifest digests with constants embedded in a few consumers proves internal duplication, not completeness of the production trust boundary.

For each production operation, build a matrix of:

```text
operation -> production owner -> executable/helper bytes -> manifest entry -> pre-side-effect check -> authenticated execution copy/path
```

Then verify:

- every executable script, helper bundle, plugin commit, package tree, and external binary that can reach a production side effect is represented or explicitly excluded with rationale;
- the manifest's plugin commit/version matches the commit actually archived or materialized by production code;
- package-tree hashes are independently recomputed with the exact canonical algorithm used by the consumer;
- symlink resolution, final path, file type, mode, UID/GID, link count, and writable parent-path ownership are recorded alongside the digest;
- the same bytes that were checked are the bytes executed. Prefer copying verified bytes into a private generation or an fd-bound execution seam; a `read/hash -> execute mutable pathname` gap remains a TOCTOU question and must not be waved away by a matching digest;
- contract tests enumerate all production consumers and fail when a new runtime pin or owner is added without a manifest mapping.

Treat an omitted production owner or unauthenticated runtime dependency as `BLOCKED`, even when every currently listed manifest hash matches.

## 7. Preserve the required report before spending the final tool budget

For independent frozen reviews, create the report at the approved output path immediately after the start pin succeeds. Record the immutable identity and an initial `BLOCKED_PENDING_REVIEW` status, then append evidence as lanes complete.

Before expensive broad searches or full suites:

1. reserve calls for the end verifier and final report update;
2. write confirmed blockers as soon as they are independently reproduced;
3. run the end verifier before any clean conclusion;
4. finalize the saved report before composing the chat response.

Treat closure calls as a hard budget, not an aspiration. Batch independent source reads and test-name discovery; consolidate custom negative probes into one external runner where practical. Once the required full suite and invariant matrix are complete, stop optional browsing and execute, in order: any still-required repeat probe, end verifier, immutable-identity comparison, formal report replacement, and report checksum. Do not spend the reserved closure budget creating extra one-off evidence scripts after equivalent evidence is already sufficient.

If tool budget becomes uncertain, preserve a formally end-labelled `BLOCKED` report with the exact missing closure rather than merely leaving an interim file and explaining the gap in chat. The report is the deliverable; the chat summary is secondary.

A tool ceiling must interrupt a `CLEAN` claim, but it should not erase already collected evidence or leave a user-requested report unsaved. If the end verifier or full evidence matrix is missing, preserve the report with verdict `BLOCKED` and name the missing closure explicitly.
