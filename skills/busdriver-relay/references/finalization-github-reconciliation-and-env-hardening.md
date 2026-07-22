# Finalization: GitHub Reconciliation and Environment Hardening

Use this reference when Delivery Mode can create a PR, merge a PR, push a branch, or invoke a read-only PR-grind checker. The core rule is: **bind every observation and mutation to one explicit repository identity and reconcile irreversible effects from remote state.**

## 1. Derive repository identity without ambient selectors

- Read the **effective repository-scoped** origin under the same sanitized Git environment used for mutation. Do not use `--local` alone: with `extensions.worktreeConfig=true`, `config.worktree` can override `remote.origin.url`, command helpers, credentials, and URL rewrites while bypassing local-only inspection.
- Disable system/global config for this lookup, but include both common-repository and worktree config; require exactly one non-empty effective URL.
- Test a common-config safe origin plus a worktree-scoped attacker origin/`core.sshCommand`; identity and mutation safety must fail closed.
- Accept only exact GitHub URL forms that yield a validated `owner/repo` slug (HTTPS, `git@github.com:`, or `ssh://git@github.com/`).
- Fail closed on multiple URLs, URL rewrites, `pushurl`, non-GitHub hosts, malformed slugs, or an unreadable local config.
- Never use ambient `GH_REPO`, `GH_HOST`, `gh repo view`, or an inherited Git config as repository authority.

Every `gh pr view`, `gh pr checks`, `gh pr create`, and `gh pr merge` call must include `--repo owner/repo`. REST calls must use an explicit `repos/{owner}/{repo}/...` endpoint. GraphQL calls must pass validated owner/name variables.

## 2. Sanitize subprocess environments

Before Git/GitHub helpers or PR-grind child processes run, remove ambient selectors and command overrides, including:

- `GH_REPO`, `GH_HOST`
- `GIT_CONFIG_*`
- `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, object/common-dir overrides
- `GIT_SSH`, `GIT_SSH_COMMAND`, proxy-command overrides
- `GIT_ASKPASS`, `SSH_ASKPASS`

Use an allowlist rather than a growing denylist. Preserve only the minimum locale/temp/runtime variables and the exact authentication variables required by the specific trusted network process. Use a fixed trusted executable search path or resolved trusted executable; never preserve arbitrary `PATH`, opaque sentinel variables, or interpreter/shell startup injection such as `BASH_ENV`, `ENV`, `ZDOTDIR`, `PYTHONPATH`, or `PYTHONHOME`. Launch Python policy children with isolated mode (`python -I`) where supported. Local text-transform/helper scripts must not receive GitHub tokens, SSH-agent access, HOME, or unrelated credentials.

Only re-add a validated `GH_REPO=owner/repo` for a command that also carries an explicit `--repo` or explicit REST endpoint. Do not use the environment variable as the sole binding.

Treat executable checker/helper paths as part of the credential boundary:

- live PR-grind must use the bundled, resolved checker path; arbitrary `--check-script` paths are fixture/test-only;
- plugin helper scripts must come from a validated Busdriver root with expected package identity, regular non-symlink files, **and authenticated content provenance**: canonical path/name checks alone are insufficient. Require a trusted checkout/commit plus tracked-clean required files, or pinned digests/signatures; revalidate immediately before execution. Add negative tests that replace each helper with a malicious regular file at the canonical path;
- do not accept ambient `BUSDRIVER_PLUGIN_ROOT`/`CLAUDE_PLUGIN_ROOT` as live authority without the same validation;
- child scripts that only transform supplied text should receive a minimal environment without GitHub tokens; preserve credentials only for a trusted helper that genuinely calls GitHub.

A command mock that records only argv is insufficient for these paths: assert the child environment omits selectors/overrides and that an untrusted executable path is rejected before launch.

For mutating finalization, also inspect repo-local config and block values that can redirect execution, invoke helpers, or leak credentials/source data, including:

- `core.hooksPath`, `core.askPass`, `core.fsmonitor`, `core.attributesFile`
- `credential.*`
- `core.sshCommand`, `core.gitProxy`
- `remote.*.(receivepack|uploadpack|proxy)`
- **all** `http.*` entries (not only scoped `http.<url>.extraHeader`; unscoped `http.extraHeader` and `http.proxy` are common bypasses)
- `filter.*`, `gpg.*`
- `url.*`, `include.*`, `includeIf.*`

Git normalizes config key names to lowercase in `git config --name-only` output; match normalized names such as `core.hookspath`, `core.sshcommand`, and `includeif.*`. Tests must include both scoped and unscoped HTTP forms.

Do not forget default `.git/hooks`: blocking only `core.hooksPath` does not stop `pre-commit`, `commit-msg`, or `pre-push`. A sanitized environment limits credential exposure but does **not** prevent a hook from reading and exfiltrating repository contents. Prefer defense in depth for finalization:

1. Preflight the Git common directory's default `hooks/` directory (linked worktrees may not keep hooks under the worktree-specific git dir); ignore only inert `*.sample` files and fail closed on executable hooks, symlinks, or an unreadable hooks directory.
2. Also apply a command-level `-c core.hooksPath=/dev/null` override to the actual finalization `commit` and `push`. Preflight alone has a check-to-execution race, while the command-level override closes that race.
3. Keep lower-level commit helper tests capable of running hooks so hook mutation/restoration defenses remain covered, but make the production finalization call explicitly opt into hook disabling.

## 3. PR creation protocol

Under the finalization lock:

1. Re-run Delivery Status and verify immutable review/litmus evidence.
2. Resolve validated repo slug, head owner/branch, base branch, and reviewed local HEAD.
3. Verify the remote branch head equals the reviewed local HEAD.
4. Query matching PRs using explicit repo, head, and base. Record the number set of **every PR returned by the precondition query**, not only those that are exact matches at that instant; block only an exact open duplicate. A pre-existing PR can change fields between queries and must never be misattributed as the new effect. A historical closed PR must not permanently prevent a new PR.
5. Immediately before `gh pr create`, re-read local HEAD and remote branch head. Abort if either changed.
6. Run `gh pr create --repo ... --head ... --base ...`.
7. Regardless of command exit status, query GitHub again and compare against the precondition identity set. Reconcile only a **new** PR number that did not exist in the precondition snapshot and whose:
   - head SHA equals the reviewed SHA;
   - head repo equals the validated repo;
   - base ref equals the reviewed base;
   - base repo equals the validated repo;
   - state is `open` for a normal successful postcondition.
8. Record PR number and URL only from that new reconciled remote snapshot. Never let a historical closed PR with the same branch/base/SHA impersonate the current command's effect.

Classification:

- command success + one new exact open remote match: `pr_created`, `ok=true`;
- command failure + one new exact open remote match: effect is `pr_created`, but `ok=false` with a reconciled postflight-failure reason;
- one new exact match that is already non-open: preserve that the side effect occurred, but return `ok=false` with a non-open postcondition warning;
- only a pre-existing closed exact match remains: the create did **not** reconcile; report command/postcondition failure rather than `pr_created`;
- no new exact match after reported success: postcondition failure;
- query unavailable or multiple new exact matches: outcome uncertain, fail closed.

For completed-but-warning outcomes, keep the operation step marked completed/passed and mark the postflight reconciliation step failed. Do not emit a generic `blocked/skipped` step sequence after remote state proves the effect happened.

## 4. Merge protocol: immutable base binding is mandatory

`gh pr merge --match-head-commit` atomically binds only the head commit. It does **not** bind the reviewed base repository, base ref, or base OID. A PR can be retargeted, or its base can advance, between the final snapshot and direct merge; discovering that only in postflight is too late.

Therefore:

1. Normalize any user base form (`main`, `origin/main`, `refs/heads/main`, `refs/remotes/origin/main`) to one canonical branch, or derive it from the trusted PR snapshot when omitted.
2. Bind the operation to exact head repo/ref/OID and base repo/ref/OID.
3. Permit mutation only through a server-side mechanism that atomically enforces those bindings, or through a merge queue whose current merge-group checks provide the required base semantics and are explicitly verified.
4. If the available API/CLI can enforce only expected head OID, direct merge must fail closed with a precise unsupported-atomic-binding reason. Re-querying immediately before merge narrows but does not close the race.
5. Once an atomically bound mechanism exists, reconcile the completed remote effect after any command exit status and preserve completed-but-warning outcomes.

Do not weaken this to “preflight checked base ref” or “postflight will detect retargeting.” Neither prevents an unsafe irreversible effect.

## 5. Push protocol: an unchanged base ref is not an atomic lease

A local Git probe against a private bare remote established an important receive-pack property: even with `git push --atomic`, an exact `--force-with-lease` for the reviewed base, and an explicit `reviewed-base:base-ref` refspec, Git may omit the unchanged base ref from the receive command set. A `pre-receive` hook can then advance the base while the feature ref is still accepted. The client-side lease check does not make the omitted no-op base part of the server transaction.

Therefore:

1. Do not claim atomic reviewed-base binding merely because the push argv contains the base refspec and lease.
2. A pre-push base query plus post-push reconciliation narrows the race but does not prevent the feature ref side effect from occurring against a different base.
3. Keep production branch push non-dispatchable unless a server-side mechanism can transactionally compare the exact reviewed base OID while creating/updating the exact feature ref, or an explicitly approved quarantine-ref protocol makes a stale-base side effect harmless and fully reconcilable.
4. Preserve an explicit `already_up_to_date` no-op when the remote feature ref already equals the reviewed head; a no-op must not inherit mutating authority or run push.
5. Keep a deterministic regression that records the actual receive command set and proves an unchanged base can be omitted; a mock that only checks argv is insufficient.

When the hosting provider cannot supply the required multi-ref compare-and-swap primitive, report `atomic_push_base_binding_unavailable` as a policy boundary rather than silently falling back to check-then-push.

## 6. Machine output, idempotency, and authority-state integrity

- Never parse a diagnostic tail as complete machine JSON. Capture full stdout separately with a strict size bound, parse that buffer, then remove it from persisted/redacted effects; retain only the tail for human diagnostics. Tests need valid API objects larger than the tail limit.
- Treat push as idempotent: if the remote branch already equals the reviewed local head, return an explicit `already_up_to_date` no-op and do not run push or ancestor checks that can misclassify equality.
- Pin push to the validated literal destination URL, revalidate effective config and destination immediately before the side effect, and do not reuse a mutable remote name after checking it.
- A commit caller must not infer completion merely because ambient `HEAD` changed. Require the commit helper's verified effect (expected tree, exact parent, exact message, helper after-OID) and equality between that OID and the observed post-call HEAD.
- If an untrusted draft child can write the preflight baseline, plain JSON is not authority. Keep the baseline in parent memory or authenticate it with an HMAC/signature whose key is held only by the parent and trusted pre/postflight processes. Missing, modified, symlinked, or non-regular marker/baseline state must fail closed; test creation, removal, content change, symlink, and non-regular replacement.

## 7. Lock and outcome discipline

- Keep the finalization lock through the postcondition query and outcome classification.
- Record `completed`, `not completed`, or `uncertain` before releasing the lock.
- A completed effect followed by local drift remains completed; report the drift separately and never overwrite external changes to manufacture a clean result.
- Treat local cleanup errors as outcome ambiguity. For example, a merge command may complete remotely and then fail while checking out/deleting a branch because another worktree owns the base branch. Re-read the PR state, merge commit, remote base ref/tree, and remote branch before retrying; never issue a second merge solely because the CLI exited nonzero.
- No push/PR/merge is allowed before targeted regressions, the complete contract suite, diff checks, and independent correctness/security review are green.

## 8. Regression-test matrix

Include realistic remote snapshots in mocks; a plain `{ok: true}` command mock is insufficient once reconciliation is mandatory.

Minimum tests:

- ambient `GH_REPO`/`GH_HOST` cannot redirect queries;
- multiple or malformed local origin URLs fail closed;
- dangerous repo-local Git config is rejected, including unscoped `http.extraHeader`, `http.proxy`, executable filters/fsmonitor, credentials, and hook redirection;
- local or remote head changes immediately before PR creation block the side effect;
- PR create succeeds only after exact postcondition reconciliation;
- non-zero PR create reconciles an actually new PR;
- a pre-existing closed exact PR cannot be mistaken for the current create effect;
- a newly created but non-open PR is preserved as an effect with failed postflight;
- worktree-scoped config overrides (`config.worktree`) are included in identity and mutation-safety checks;
- machine JSON larger than the diagnostic-tail limit parses from the bounded full-output channel;
- commit completion requires the helper-verified OID/tree/parent/message, not ambient HEAD drift;
- push equality returns an explicit no-op and performs no mutation;
- merge rejects wrong repo/head/base/state and fails closed when immutable base binding is unavailable;
- a race that retargets or changes the base between snapshot and attempted merge cannot produce a direct merge side effect;
- when an atomically base-bound merge mechanism is implemented, non-zero command results reconcile an actually completed merge;
- unavailable or ambiguous postcondition queries produce an uncertain blocked result;
- PR-grind child processes scrub ambient selectors;
- PR-grind envelopes reject repository-binding mismatch;
- live PR-grind rejects an untrusted checker/helper path before execution.

Mocks for stateful APIs must model the full sequence: precondition query first, side-effect command second, postcondition query third. For PR creation, return the pre-existing identity set on the first query and the old-plus-new set on the second; for merge, return the exact open PR first and the same exact closed/merged PR second.

When hardened Git commands include global options such as `git -c core.hooksPath=/dev/null push ...`, do not write mocks that recognize only `cmd[:2] == ["git", "push"]`; they silently stop simulating the side effect. Assert the full security option and locate the Git subcommand after global options (or use a small argv parser). Add a regression proving an executable default hook is both rejected by mutation preflight and not executed by the command-level override.

Run targeted RED tests first, implement the smallest hardened path, then run the entire affected contract file and the full suite. **Any code or test change made after a green full-suite run invalidates that evidence**: rerun diff/syntax checks, the complete suite, and independent review against the final diff before remote mutation.