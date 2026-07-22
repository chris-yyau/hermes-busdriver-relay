# Frozen production trust-boundary review: ownership and blocker-ordering probes
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference for an independent, fail-closed review of a frozen candidate that claims production dispatch blockers, trusted-runtime ownership, and documentation truth.

For concrete regressions covering transitive helper ownership, top-level mutation blockers, outer smoke/probe launchers, pre-blocker executable lookup, tracked project guides, and report-digest sidecars, continue with `frozen-production-transitive-ownership-lessons.md`.

## Core rule

A policy blocker is only effective at the boundary it claims to protect when it runs **before every protected interaction**, not merely before the final worker subprocess. Treat any earlier repository read, HOME/state access, credential discovery, lock acquisition, helper invocation, or artifact write as a boundary crossing.

## Review sequence

1. Run and save the frozen start verifier before inspecting the candidate. Record complete manifest, patch/tar/tree, HEAD, branch, tracked/untracked counts, and verifier output outside the candidate.
2. Create the review report immediately with a fail-closed interim verdict. Update it as soon as a blocker is confirmed; do not wait for the end of a long audit.
3. Trace each production entrypoint from argument parsing to its blocker. Inspect both direct runtime wrappers and outer launchers. A direct Pi/OpenCode wrapper that blocks before `--repo` handling does not prove the outer launcher has the same ordering.
4. Probe with a throwaway repository, synthetic HOME, fake worker sentinel, and harmless FIFO credential files. Assert all of the following independently:
   - exact blocker/reason;
   - worker sentinel absent;
   - repo unchanged;
   - no run/state/lock directories created;
   - no HOME or credential-file access/hang;
   - bounded completion.
   Add a durable unit-level ordering contract too: load the production entrypoint without executing it, replace every downstream prerequisite (`git_root`, state/HOME resolution, lock, prompt, gate, run-directory, worker, postflight, and report persistence) with a fail sentinel, invoke `main()`, and require the fixed blocker envelope. This catches reorderings that a nonexistent-path probe may miss. The production blocker must have no CLI or environment unlock; a non-installed runpy harness may replace it only in memory for contract tests.
5. For verifier containment, verify the blocker precedes delivery-status, PR-grind, repo helpers, auth, and verifier command execution. Patch or monkeypatch sentinels around all helper seams when possible; output reason alone is insufficient.
6. For push, PR creation, and merge, trace the exact atomic base/head binding blocker and confirm no credential-capable or mutating path can bypass it.
7. Audit fixture seams in both directions: production must not import or select them through flags/environment, and fixtures must be clearly non-installed. Preserve lower-level contract testing through explicit test-only dependency injection rather than production bypass flags.
8. Run the end verifier and compare every frozen identity field with the start record. Any drift, missing test, unfinished probe, or blocking finding means `BLOCKED`, never `CLEAN`.

## Trusted-runtime ownership closure

A manifest is not ownership proof merely because its hashes match. Build a closure from each production entrypoint through every interpreter, executable, helper, materializer, and imported package:

- Search for bare subprocess names such as `git`, `gh`, `node`, `python`, `bash`, and `jq`.
- Resolve each command under the **actual child environment and PATH order**. Compare the resulting binary and SHA-256 with the manifest pin.
- Treat a helper that pins `/opt/.../git` but later executes bare `git` under a PATH preferring `/usr/bin` as an ownership break.
- Apply this especially to authenticated snapshot materialization: the executable performing `git archive`, integrity checks, commit lookup, and package-version extraction must itself be manifest-bound. Add a control-flow regression that records calls to the authenticated executable resolver, replaces the child `PATH` with a fake same-name executable that writes a sentinel, and proves materialization succeeds through the absolute trusted path while the ambient sentinel stays absent.
- Verify commit existence and read the package version from the pinned commit, not only from the ambient checkout.
- Hash package trees with entry-type binding. Include regular files, directories when semantically relevant, and symlink target text; a digest that silently skips symlinks may omit executable/import-relevant state.
- Check that manifest constants are actually consumed by production control flow. Tests that only compare JSON values to source constants do not prove runtime use.

## Documentation truth and semantic mutants

Inventory documentation from the primary SKILL/README links, not from a hand-selected test tuple. Classify every linked reference as one of:

- active/current and required to state the blocker;
- historical/provenance with an explicit superseded/non-production banner;
- target-state/design, clearly separated from current production behavior.

Current references that say a launcher "works", "may mutate", or is the current/default worker contradict a production-disabled policy unless they explicitly scope that statement to a non-installed fixture or route metadata.

Semantic mutant tests must cover the complete active/current inventory and reject at least:

1. an enabled production-dispatch claim;
2. a blocker plus contradictory positive sentence in the same document;
3. a historical smoke transcript presented as current production proof;
4. omission of the blocker from a newly linked current reference.

A mutant harness that catches contradictions only in three curated files does not protect ninety linked current references. Define one authoritative active-policy document set and reuse it for blocker-presence, exact stale-phrase, and semantic checks. Parametrize every active document against every required mutant, and make the clean-document assertion run before appending the mutant so a pre-existing failure cannot create a false-positive mutation pass. Add inventory assertions so newly linked current references cannot escape coverage.

## Evidence and tool-ceiling discipline

- Store probes and reports outside the frozen candidate.
- Never modify the candidate to demonstrate a finding.
- Redact credentials and use synthetic sentinels only.
- Save exact commands, exit codes, elapsed time, observed filesystem effects, and hashes.
- If a tool-call ceiling interrupts before targeted/full tests or the end verifier, mark the report incomplete and `BLOCKED`; do not invent the missing SHA-256 or imply end-boundary closure.
