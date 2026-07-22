# Frozen correctness and state-integrity review

Use this for an independent frozen-candidate correctness lane, especially when the verdict is strictly `CLEAN` only with zero blocking findings.

## Review sequence

1. **Authenticate and reconstruct first.** Run the lane-specific frozen verifier before reading or testing. Record manifest, patch/source hashes, source HEAD, candidate tree, record counts, and `SNAPSHOT_OK`.
2. **Use a hermetic review environment.** Give each verifier/test/probe a fresh temporary `HOME`; pin the isolated Git config; set `GIT_CONFIG_NOSYSTEM=1` and `PYTHONDONTWRITEBYTECODE=1`; run pytest with `-p no:cacheprovider`.
3. **Review seams, not just files.** Trace path-scope semantics, state transitions, rollback/CAS ownership, reconciliation after ambiguous side effects, lock owner/token/staleness, refusal paths, and producer-to-consumer metadata trust boundaries.
4. **Run targeted and full tests.** Target the high-risk contract modules first, then run the complete suite. Passing tests are evidence, not a CLEAN verdict.
5. **Add read-only negative probes.** Load candidate scripts in-process with `runpy.run_path` or invoke them against temporary fixtures. Keep all generated config/state outside the candidate. Probe segment-aware globs, malformed/missing metadata, concurrent/CAS cases, stale-lock ownership, and network-mutation refusal.
6. **Re-run the exact same frozen verifier.** The final candidate tree and artifact hashes must equal the initial authenticated values. Some verifiers deterministically rebuild and stage the review candidate to compute the tree; distinguish this expected verifier behavior from source/artifact drift.
7. **Write a reproducible report.** Include verdict, blocking findings with file/line evidence, commands, outputs/counts, negative-probe results, artifact/tree hashes, remediation criteria, and report checksum.

## Permission/proof metadata rule

Treat fields such as `programmatic_dispatch_allowed`, `adapter_verified`, `mutation_allowed`, and finalization authority as proof-like state:

- Every authoritative producer entry must explicitly declare them with the correct type.
- Never normalize a missing permission/proof field to `true`.
- A consumer that rejects missing fields is insufficient if its trusted producer first synthesizes those fields with permissive defaults; the producer has erased the evidence of omission before the trust boundary.
- Producer contract tests must validate the source declaration map itself, not only the normalized output. Add mutation/negative tests that delete each permission field and assert the result cannot become positive.
- Resolver-ready, selected-agent-present, and adapter-verified are separate facts. Do not infer dispatchability from route resolution alone.

## High-value negative probes

### Segment-aware path scope

Use a shared matrix against every implementation of the matcher:

- `src/*.py` matches `src/a.py` but not `src/nested/a.py`.
- `src/**/*.py` matches both direct and nested files.
- `docs/?.md` matches one-character basenames only.

A consistent matrix catches drift between gate, Pi, and OpenCode wrappers.

### Producer/consumer metadata completeness

Inspect the producer's authoritative role map before normalization. For every role, assert permission/proof fields are present and boolean. Then invoke the real producer and ensure omission does not become a positive value. Finally pass malformed/missing/contradictory payloads through the resolver and require fail-closed output.

### State ownership and ambiguous side effects

Exercise:

- ref CAS failure and CAS rollback without overwriting a concurrent commit;
- hook-created or concurrently recreated tracked, staged, and untracked paths;
- ambiguous push/result reconciliation rather than claiming success;
- lock release requiring owner token and compare-delete protection;
- stale locks requiring explicit recovery rather than automatic takeover;
- PR-create/merge refusal before any network mutation when atomic binding is unavailable.

## Verdict discipline

- `CLEAN`: zero remaining blocking findings and complete initial/final provenance evidence.
- `BLOCKED`: any reproducible blocker, unresolved critical seam, provenance drift, or missing required evidence.

Do not let a green full suite override a negative probe that demonstrates a fail-open state transition or an integrity gap; explain why existing tests encode or miss the unsafe behavior.