# Production fail-closed seams and frozen provenance
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this reference when a relay candidate blocks unsafe production dispatch but still needs executable adapter contracts in tests, or when freezing a candidate from an isolated worker clone.

## Prove the real production launch path

An environment/PATH guard is not containment. A weak RED test can give false confidence if its fake `git` exits immediately and the wrapper stops at `repo_state_unavailable` before reaching the worker launch.

For an adversarial production test:

1. Supply the exact apparently-valid guard environment accepted by production.
2. Make the fake guard `git` proxy the real trusted Git executable so repository discovery succeeds; keep `gh` executable but non-mutating.
3. Point the worker argument at a fake executable that writes a sentinel as its first action.
4. Require the exact production policy blocker, not a downstream parse/result error.
5. Assert the sentinel is absent, credentials were not read/copied, and pre-block run artifacts do not exist when the contract promises side-effect-free rejection.

A downstream error such as `opencode_result_missing` with a present sentinel proves the worker launched and the containment claim is false.

## Block at every production decision surface

A wrapper-level blocker is insufficient when an outer gate or dispatcher still advertises or attempts dispatch. Keep all production surfaces coherent:

- status/capability metadata: dispatch false, adapter unverified, exact blocker;
- state gate decision: `agent_implementation_draft_allowed=false` and overall production result blocked;
- agent dispatcher: stop at preflight before constructing or launching the wrapper command;
- Pi/OpenCode wrapper: independently fail before worker launch or credential handling;
- verifier and PR-create surfaces: independently fail before command/network mutation.

This layered block prevents a future caller from bypassing an outer policy assumption by invoking a lower production script directly.

## Non-installed runpy fixture pattern

Preserve adapter/schema/scope tests without creating a production bypass:

- Put the harness under `tests/fixtures/`, never under an installed scripts directory.
- Load the production script with `runpy.run_path` and replace a narrow function such as `production_dispatch_blocker` in that loaded namespace.
- Do not add a production parser flag, environment variable, config key, or magic executable name that disables the blocker.
- If tests use both subprocess execution and `runpy` helper inspection, make the fixture execute `main()` only when `__name__ == "__main__"`; otherwise export the loaded production namespace.
- Add a production-path regression that uses the real production script constant, so changing the general test constant to the fixture cannot accidentally erase fail-closed coverage.

## Freeze provenance from worker clones

A child clone's `origin` may point to the local source repository. Its `refs/remotes/origin/main` can therefore represent the source repo's local `main`, not canonical GitHub `origin/main`.

Before writing a frozen manifest:

1. Record candidate bytes, HEAD, and branch from the worker clone.
2. Record canonical remote URL and canonical tracking ref from the original boundary-bearing repository (and later revalidate the network remote before delivery).
3. Build the candidate tree through a temporary index; never stage the worker's real index.
4. Include tracked plus untracked files and executable modes in a deterministic source tar.
5. Reconstruct outside the source repo, regenerate the patch, and compare the exact candidate tree.

## Verify the verifier

A new fixture changes path and untracked counts. Update all verifier invariants, then run the verifier yourself before dispatching reviewers.

- A verifier assertion bug is not automatically candidate drift. Diagnose only in an external debug copy; do not mutate frozen candidate bytes or artifacts.
- Every review lane gets a unique external reconstruction directory and runs the boundary check at both start and end.
- Run the full suite and critical adversarial nodes in the rebuilt candidate, not only in the mutable source worker.
- Any candidate byte edit requires a new frozen version and fresh reviews; never repair the previous frozen source in place.
