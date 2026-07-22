# Security and Data-Egress Review of Draft/Finalization Surfaces
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this checklist for read-only reviews of Busdriver relay launchers, Delivery Mode executors, and GitHub finalizers.

## 1. Establish the immutable review scope

- Capture `HEAD`, `origin/main`, merge base, changed-file list, and initial worktree status separately; avoid compound commands whose early failure hides later output.
- Attribute findings only to `origin/main...HEAD`. Use unchanged code only to explain reachability.
- Recheck worktree status after probes/tests. If unrelated edits appear, treat them as concurrent work: exclude them, report them, and do not restore or overwrite them.
- Run tests without repository caches where practical: `PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider ...`.

## 2. Treat PATH wrappers as advisory, never as an authority boundary

A wrapper that inspects only `$1` or `$1 $2` is bypassable through global options and indirection:

- `git -C <repo> push`
- `git --git-dir=<path> commit`
- `gh --repo OWNER/REPO pr create`
- absolute executable paths, `env`, shell indirection, aliases, or a child-reset `PATH`

Use a temporary fake underlying binary and assert blocked forms return the guard's deny code; a distinct fake-binary code proves the wrapper forwarded the command. Also test direct invocation of any finalizer executable from the draft process. A postflight check and an authority-false JSON written by the same worker cannot prove that remote side effects did not already occur.

Safe designs require an OS sandbox/capability broker, network and credential isolation, or an unforgeable one-shot operator capability checked by the finalizer. Do not describe a PATH shim as fail-closed enforcement.

## 3. Verify the caller boundary, not merely CLI intent

A finalizer must not infer `explicit_user_request` solely from `--mode execute --operation ...`. Check whether a draft agent can launch the finalizer directly, reset its environment, or call a trusted writer. Require a capability that the worker cannot mint and bind it to operation, repo, branch/HEAD, expiry, and intended remote side effect.

## 4. Marker and review evidence need provenance

Content, filename, mtime, `PASS`, diff hash, and timestamp establish freshness but not authorship. A repo-writing agent can often compute all of them.

Check that authority evidence is bound to:

- trusted writer/reviewer identity and independent session/run ID;
- canonical repo root and remote repository ID;
- current HEAD, staged-tree or branch-diff hash, and base ref;
- freshness window and one-shot nonce;
- an append-only or otherwise worker-inaccessible ledger.

If preflight records markers, ensure postflight compares that baseline. A later executor must distinguish trusted-writer output from a byte-identical file created by the worker. Symlink, regular-file, traversal, and size checks are necessary but do not provide provenance.

## 5. Audit Git local configuration and hooks as executable input

Disabling global/system Git config does not disable local `.git/config`. Review at least:

- `core.hooksPath` and all effective commit/push hooks;
- `core.sshCommand`, credential helpers, remote helpers, and URL rewrites;
- `remote.*.pushurl`, mirror/refspec/push options;
- `remote.*.gh-resolved` and other GitHub CLI repo-selection state.

A gate that hashes only `.git/hooks` misses hooks redirected through `core.hooksPath`. Verify relevant local config and effective hook files both before and immediately before finalization. Run trusted hooks with a minimal environment; do not expose provider/GitHub credentials to arbitrary repository hooks. Tree/message postconditions cannot detect hook-based network egress that leaves the worktree unchanged.

## 6. Bind every GitHub read and write to the same repository

Do not rely on cwd inference for `gh pr view`, checks, reviews, comments, or GraphQL while pinning only the final merge/create command.

- Resolve the intended repository from a validated remote once.
- Pass explicit `--repo` or a controlled `GH_REPO` to every GitHub read and write.
- Include repository ID/slug, PR number, URL, base, and head SHA in evidence envelopes.
- Validate those fields before mutation.

`--match-head-commit` binds only the commit SHA. The same SHA can exist in another repository with different CI, review, and branch-protection state.

## 7. Reconcile ambiguous remote outcomes

A timeout or nonzero exit does not prove a remote side effect failed. After every failed/timed-out push, PR create, merge, release, or similar operation, query the pinned remote postcondition and classify:

- completed;
- not completed;
- outcome uncertain.

For PR creation, query exact repo/head/base and avoid duplicates. For merge, verify merged state, `mergedAt`, and merge commit/head identity. Preserve the lock and durable transcript until reconciliation is recorded. Never label an irreversible operation simply `blocked` when completion is unknown.

## 8. Test redaction with a synthetic credential corpus

Exercise every path that reaches stdout, stderr tails, exception strings, command arrays, JSON artifacts, and status lookup. Include synthetic examples for:

- classic and fine-grained GitHub tokens;
- Bearer and Basic Authorization;
- provider/API tokens and JWT-like values;
- URI userinfo credentials;
- split argv forms such as `--token VALUE`;
- secret-bearing dict keys and nested lists/objects.

Prefer allowlisted artifact fields and omission of sensitive command/body material over regex-only blacklists. Apply redaction before persistence and before console output; use restrictive file modes as defense in depth, not as a substitute.

## 9. Parent-only keys and authenticated helper closure

A key is not parent-only if it is placed in a gate/helper child environment, even when grandchildren and verifiers cannot see it. Review the complete secret flow, including env, argv, stdin, files, crash output, and child inheritance.

- Keep signing/HMAC computation and verification in the parent. Let helpers emit canonical unsigned data.
- Never execute a key-bearing child from a pathname that was merely hashed earlier. A same-UID process can replace the file between verification and exec and receive the key.
- A manifest pin is not an execution identity. Prefer open-and-hash followed by execution from the same FD, or a content-addressed immutable runtime image.
- Pin the complete transitive dispatch closure: entrypoint, lock helper, gate, wrapper, adapters/tools, schemas, interpreter, package tree, and dynamic imports. Tests must fail when any one is omitted or swapped after verification.
- Resolve `git`, `gh`, interpreters, and runtimes from the authenticated manifest, never ambient `PATH` captured before environment scrubbing.

## 10. Read-only status must not become an execution or egress surface

A command labelled `read_only` must not execute scripts from the inspected plugin/repository. Static status probes that run `<plugin>/resolve-*.sh` inherit an attacker-controlled code boundary and may also honor `BASH_ENV`, `ENV`, `PATH`, credential, HOME, XDG, or SSH-agent state.

- Parse static config instead of dispatching inspected code.
- If execution is unavoidable, authenticate/materialize the helper and use a minimal `env -i` with private HOME/XDG and fixed executable paths.
- Use `lstat`/`O_NOFOLLOW` plus post-open `fstat` for marker, lock, and status files. `exists()`, `stat()`, `is_file()`, and `read_text()` follow symlinks.
- Do not emit marker previews or arbitrary lock JSON. Return allowlisted metadata/digests and redact before persistence/output.
- Reject FIFOs, devices, sockets, symlinks, and multi-link write targets. Protect every parent component descriptor-relatively; leaf-only `O_NOFOLLOW` does not stop parent-directory swaps.

## 11. Bound before capture, parse, and persist

Applying `tail()` or a schema after `capture_output=True`/`read_text()` is not a resource bound: the complete attacker-controlled stream/file has already entered memory.

- Stream stdout/stderr with a hard byte cap and terminate the child when exceeded.
- Open artifacts with `O_NOFOLLOW`, `fstat` size/type before reading, and enforce JSON depth, total decoded bytes, array counts, and string lengths.
- Redact before writing raw logs or artifacts, not only in the final response envelope.
- Use unique `mkdtemp` run directories and refuse pre-existing output paths; timestamp-only reusable directories invite symlink preplacement and cross-run contamination.

## 12. Read-only proof discipline

- Use temporary repositories and fake executables for command-routing probes; remove them afterward.
- Never contact GitHub for a mutation probe.
- If the user requires zero mutation, do not run tests that may create caches/artifacts; rely on no-cache settings only when temporary writes are explicitly allowed.
- Run `git diff --check` and targeted contract tests when permitted, then re-attest the exact snapshot.
- Passing tests do not clear a finding when the relevant negative case is absent. Call out missing tests for global-option bypasses, direct-finalizer invocation, marker forgery, `core.hooksPath`, cross-repo PR evidence, remote timeout reconciliation, redaction variants, runtime swap-after-hash, parent-directory symlink swaps, FIFOs/devices, and oversized stdout/JSON artifacts.
