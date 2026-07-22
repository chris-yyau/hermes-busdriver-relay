# Frozen repair workers and verification isolation

Use this when a blocked frozen review must be repaired in a new generation, especially when the repair worker is reconstructed from a verifier-created candidate.

Companion references:

- `frozen-state-integrity-policy-ordering.md` — frozen state and policy ordering.
- `frozen-review-auth-docs-runtime-identity-hardening.md` — ambient auth, semantic-doc mutants, and runtime identity.
- `frozen-production-trust-boundary-ownership-review.md` — early blockers, PATH ownership, linked-doc closure, and tool-ceiling evidence.
- `frozen-review-continuation-and-evidence-recovery.md` — interrupted/missing reviewer lanes.

## 1. Normalize the repair worker without changing candidate bytes

A rebuilt review candidate may carry review-only Git metadata even though its working-tree bytes are correct:

- the index may contain every candidate path staged;
- `origin` may still point at a temporary/local source clone;
- `origin/main` may be absent even though the frozen manifest recorded it.

In the **new isolated repair worker only**:

1. Record the frozen candidate tree.
2. Clear the inherited review index with a mixed reset that preserves working-tree bytes.
3. Recompute the candidate tree through a temporary index and require it to equal the frozen tree.
4. Rebind `origin` to the canonical remote, fetch only the canonical base ref, and verify HEAD/base/merge-base/ahead-behind.
5. Never perform these metadata repairs in the immutable frozen source or a reviewer lane.

Treat a staged rebuilt candidate as review machinery, not as delivery approval.

## 2. Keep synthetic probe environments command-scoped

Hermes terminal shell state can persist across calls. A probe that exports fake `HOME`, `PATH`, XDG, state directories, or synthetic auth sentinels can silently contaminate a later smoke/full-suite run.

Prefer a subshell or command-scoped environment:

```bash
(
  HOME="$probe/home" \
  TMPDIR="$probe/tmp" \
  XDG_CONFIG_HOME="$probe/xdg" \
  PATH="$probe/bin:/usr/bin:/bin" \
  GH_TOKEN=synthetic-sentinel \
  command-under-test
)
```

Do not leave probe variables exported in the persistent shell. Before authoritative verification, explicitly establish trusted `HOME`, `PATH`, and Hermes-only `TMPDIR`, and unset probe/state/auth variables.

If a run fails with the probe sentinel's deliberate exit code or fake executable, classify it as contaminated evidence, reset the environment, and rerun the exact command. Preserve both facts in the evidence report; never misreport the contaminated run as a product regression or quietly omit it.

## 3. Own exactly one background drafter process group

For interactive coding CLIs launched through a background PTY:

- verify that the intended CLI child actually started before sending another command;
- if the session only shows a shell prompt or launch ownership is ambiguous, terminate that tracked session and start a fresh one rather than submitting a second copy into the same PTY;
- inspect the process group before and after completion and require exactly one mutating drafter;
- when the CLI returns to a shell prompt, close/kill the tracked PTY so a deferred wrapper cannot launch a duplicate drafter later;
- before tests or freeze, require no surviving drafter/test child and review the final diff independently.

A duplicate or deferred drafter invalidates assumptions about file ownership even if tests later pass.

## 4. Freeze generator and verifier invariants

A new frozen generation must derive all counts and identities from the current source, not a prior-generation template:

- tracked count;
- untracked count;
- total source records;
- HEAD, canonical `origin/main`, branch, remote URL;
- patch/tar/manifest digests;
- candidate tree.

If a verifier is generated from an older template, replace **all** count constants dynamically. Run one debug-capable verifier invocation before the formal start lane so an assertion identifies the mismatched invariant; then run formal start and end lanes with the finalized verifier.

The verifier must:

1. authenticate manifest/patch/tar;
2. safely extract only regular relative paths;
3. compare frozen source records byte-for-byte and mode-for-mode;
4. rebuild from HEAD + binary patch + untracked records;
5. regenerate the patch exactly;
6. stage via an isolated/rebuilt index and reproduce the candidate tree;
7. recheck immutable identity at the end.

## 5. Evidence ordering

Use this order:

1. repair in the isolated next-generation worker;
2. focused RED→GREEN evidence;
3. affected modules and full isolated suite;
4. custom negative probes with command-scoped environments;
5. smoke/static/secret checks;
6. canonical remote/base normalization;
7. freeze artifacts;
8. rebuilt-candidate full suite;
9. start/end verifier closure;
10. independent same-digest review lanes.

Any source-byte edit after step 7 creates a new generation; old reviewer verdicts do not carry forward.
