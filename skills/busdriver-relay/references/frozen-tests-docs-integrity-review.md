# Frozen Tests, Docs, and Integrity Review

Use this as a fail-closed independent lane for a reconstructed/frozen Busdriver relay candidate. It complements the production-seam and operation-dispatchability references by tying suite strength, active documentation claims, and hash-cascade evidence into one verdict.

## Required dimensions

Return `CLEAN` only when all four are sound:

1. **Coverage and RED/GREEN strength**
   - Collect the suite and record the exact count before running it.
   - Run the full suite in a clean environment with Git global/system config isolated and bytecode/project caches disabled.
   - One failing or timing-dependent test blocks `CLEAN`.
   - When one node fails, reproduce that exact node under the intended interpreter, then run the remainder with only that node deselected. Report both; the remainder is not a full-suite pass.
   - Inspect whether each contract can fail for the intended regression. Presence-only substring assertions are weak evidence.

2. **Production/fixture separation**
   - Search production entrypoints for `tests/fixtures`, harness paths, test-only flags, and environment unlocks.
   - A `runpy` harness is acceptable only when it is explicit, non-installed, injects inside the test process, and production exposes no equivalent CLI/environment seam.
   - Require direct production sentinel tests proving blocked workers, verifier commands, network calls, side effects, and credential copies do not launch.
   - Never promote “fixture adapter contract passes” into “production adapter is dispatchable.”

3. **Claims truthfulness**
   - Build a capability matrix from production behavior: surface, allowed/blocked state, exact blocker, and evidence test.
   - Compare it with README, CURRENT_STATUS, canonical authority maps, skill text, adapter docs, and active ADR consequences.
   - Correct blocker text appearing somewhere in a document does not neutralize contradictory enabled wording elsewhere in that document.
   - Reject stale phrases such as “programmatically dispatchable,” “verified production lane,” or “runs verifier commands” when production fails before dispatch.
   - Historical smoke is evidence only when explicitly labeled superseded provenance.
   - Docs contracts should assert forbidden contradictions or validate a structured claim matrix, not merely require blocker-token presence.
   - Adversarially exercise negative docs contracts against temporary semantic mutants. Paraphrases such as `launches agents`, `production real-agent verification`, or `with local verifiers` must fail just as their exact blacklisted wording does. Include every current-status document and every reference the primary skill presents as current guidance; blocker text elsewhere in the file must not make a contradictory positive claim pass.
   - Keep semantic-mutant probes outside the candidate: load the actual docs-contract module with `runpy`, redirect its document-path globals to temporary copies, append one contradictory capability sentence, and call the real test function. If the test still passes, record `mutant_rejected=false` and block the lane; do not weaken the evidence by testing a hand-written approximation of the contract.

4. **Hash cascade and snapshot integrity**
   - Independently recompute every candidate-owned hash in the trusted-runtime manifest.
   - Verify consumer constants agree with the manifest and tests cover missing/tampered/mismatched entries.
   - Treat every identity field as part of the cascade, not just digest maps. For example, bind a manifest's pinned commit and package version to the production commit constant, prove that commit exists, and verify the package version plus required files at that exact commit.
   - Mutation-test the manifest contract itself from outside the candidate: point the real test function at a temporary manifest with independently changed commit/version/identity fields. If those fields can change while the test stays green, classify coverage as blocked even when the currently pinned bytes happen to match.
   - If the manifest explicitly anchors external runtime identity, also verify the actual executable bytes, package-tree digest, pinned commit existence, and files at that commit. Distinguish a trusted historical pin from the current marketplace checkout instead of assuming their HEAD/version must match.
   - Record the candidate Git tree and status before/after tests. A verifier-reconstructed candidate may intentionally store the frozen diff as staged changes; compare the exact pre/post index tree and unstaged/untracked state instead of requiring `git status` to be empty.
   - End by rerunning the same snapshot-verifier lane and record manifest hash, candidate tree, and success marker.
   - Keep scope precise in the report: state which candidate-owned and external bytes were actually verified; do not infer external runtime integrity from candidate-only contract tests.

## Isolation pattern

Use a clean environment with a fixed trusted PATH, `PYTHONDONTWRITEBYTECODE=1`, cache roots under `/tmp`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, pytest's cache provider disabled, and a **new empty HOME**. A suite passing under the operator's normal HOME is not hermetic evidence: unit tests may silently consume real GitHub/CLI credentials or configuration.

When a unit-test module must exercise code that materializes GitHub auth before its mocked network seams:

- create a per-test synthetic HOME under `tmp_path`;
- write only a clearly fake `~/.config/gh/hosts.yml`, with parent directory `0700` and file `0600`;
- use an autouse fixture only when every test in the module needs the same precondition;
- keep credential-hardening tests explicit by passing their own source path, so the synthetic default cannot weaken symlink, mode, size, or source-binding checks;
- never copy, parse, or depend on the operator's actual credential file.

A fresh `HOME` is necessary but not sufficient. The fixture must also delete ambient auth/config overrides such as `GH_TOKEN`, `GITHUB_TOKEN`, enterprise-token variants, and `GH_CONFIG_DIR` before any fake or real CLI subprocess starts. Keep tests that intentionally exercise token handling explicit: set a synthetic sentinel only inside that test after the isolation fixture runs.

Verify **review-run safety** and **fixture hermeticity** separately. Unsetting credentials in the reviewer shell protects that one run but does not prove the candidate fixture is safe in another operator shell. A useful no-secret probe injects a synthetic sentinel and observes only a presence boolean from a pytest hook after fixture setup. If the sentinel remains visible, block the candidate even when the full suite passed under reviewer-scrubbed environment variables.

Run the full suite once with that fresh HOME. If it exposes ambient-config dependencies, treat the frozen candidate as blocked even when the same bytes passed under a populated HOME. Do not create helper files or mutations inside the candidate; write reports and temporary homes outside it.

When tests run through nested shell/tool wrappers, make the evidence self-authenticating: capture pytest's immediate exit status, print `pytest_internal_rc=<n>`, and exit with that same status. If the outer tool status and the test summary/internal status disagree, rerun with this explicit wrapper before declaring GREEN. A textual `N passed` line without a confirmed zero test exit is insufficient, and an unexplained outer nonzero must not be silently ignored.

When a docs-only fix adds a previously unchanged tracked document, expect the frozen path inventory and candidate tree to change even though production code did not. Recompute tracked/untracked counts from the new manifest and update verifier assertions; never carry forward hard-coded counts from the prior digest.

## Process-timeout contract pitfall

A process-tree test with a tiny timeout and no readiness barrier may kill the parent before the grandchild writes its PID. That does not prove descendant cleanup. Use an explicit protocol:

1. The parent records the spawned grandchild PID immediately.
2. The grandchild installs the signal behavior under test, then writes a readiness marker.
3. The parent waits for readiness within a bounded startup budget.
4. Choose ordered budgets: startup allowance < worker timeout < delayed-side-effect time.
5. After timeout, assert the readiness marker existed, the process disappeared, and the delayed side effect never appeared.
6. Repeat the focused node several times before accepting GREEN; one lucky scheduler run is weak evidence.

If the readiness marker is absent, fail with that semantic diagnosis instead of falling through to a `FileNotFoundError` while reading the PID.

## Report evidence

The saved report should contain:

- `CLEAN` or `BLOCKED` at the top;
- a four-dimension verdict table;
- exact collected/full/focused/remainder test outcomes;
- file/line evidence for contradictory claims;
- production/fixture separation findings;
- independently recomputed hashes;
- final tree/verifier output and confirmation that the candidate was not modified.

Hash integrity or sound fixture separation cannot compensate for a non-green suite or false active docs.