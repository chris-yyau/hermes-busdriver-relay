# Security finalization completion discipline
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this note when a Busdriver/Hermes relay hardening task spans many tool iterations or an independent review uncovers additional blockers late in the cycle.

## Completion contract

- “Complete” means the newest diff has passed targeted regressions, the full relevant modules, the complete contract suite, static checks, secret scans, and independent re-review. Older green results become stale as soon as the diff changes.
- Do not voluntarily stop at a progress report when the user asked for completion. Keep executing until the completion contract is satisfied or the runtime forcibly ends tool access.
- If the platform enforces a tool-iteration stop, treat it as an external interruption—not a handoff and never completion. Preserve an exact resume checkpoint, then automatically resume in the next available agent turn/round without waiting for the user to say「繼續」or remind you. Do not spend that new round repeating a long status narrative: acknowledge briefly if needed and call the next tool immediately. Only stop for a genuine safety/external blocker that tools cannot resolve.
- Reserve the final mutation sequence—commit, push, PR grind, merge, cleanup—for after the newest full-suite and re-review evidence is green. A summary is not a deliverable.

## Planning long hardening loops

1. Maintain explicit checkpoints: reviewer blockers → negative tests → fixes → targeted tests → full suite → scans → independent re-review → remote delivery → cleanup.
2. Fix critical/high correctness and data-egress findings before widening scope. Avoid spending the remaining iteration budget on optional polish while blockers or full gates remain.
3. Batch independent tests and read-only reviews where possible, but serialize RED→GREEN changes. Dispatch exploratory review early, but dispatch the **final** hash-bound review only after the diff is frozen: all code, tests, documentation, smoke probes, base integration, and full gates must already be complete. Any subsequent byte change—including a test-only portability fix or ADR wording—invalidates every in-flight/final review snapshot and requires a new hash plus new review. Background dispatch is not review evidence until the result arrives.
4. After each production patch, identify which prior evidence became stale and rerun the smallest affected set immediately. Before declaring the diff frozen, run the complete suite once and fix portability flakes (for example, discover the current symbolic branch instead of hard-coding `main`) so they do not consume another review cycle.
5. When a hardening change intentionally removes a production capability, update tests by replacing obsolete positive contracts with explicit production-rejection tests and a separate non-installed dependency-injection harness where lower-level behavior still needs coverage. Do not bulk-delete failing tests merely to make the suite green. Before any scripted AST/bulk rewrite of a large, uncommitted test file, create a recoverable copy outside the repository, verify the script's input/output shape on a dry run, and inspect the resulting diff/line count immediately; prefer targeted patches when practical.
6. Reserve the final tool iterations for closing the active completion checkpoint, not composing another progress summary. If the runtime interrupts anyway, the next “continue” must resume at the first unchecked item without re-explaining prior progress.
7. Before remote delivery, fetch the base and inspect ancestry. If the topic is behind and direct rebase/merge/cherry-pick is forbidden, create a fresh worktree from the latest base, apply the cumulative reviewed diff there, and rerun gates rather than rewriting the protected WIP branch.

## Durable hardening patterns from this class of work

- Inspect effective Git config, including worktree scope; `git config --local` alone misses `config.worktree`.
- Repository identity must come from a trusted operator/preflight envelope such as `--expected-repository owner/repo`, never solely from mutable `remote.origin.url`. Compare effective origin and the actual push/API destination before lock acquisition, after the lock, and immediately before every network effect. Use the trusted slug for every explicit `gh --repo` target.
- Bind side effects to immutable identities immediately before mutation. For push, use the validated URL rather than re-resolving a mutable remote name.
- For hook-disabled finalization commits, avoid porcelain `git commit` plus rollback: a concurrent writer can move the branch and a rollback may delete its commit. Create the reviewed object with `git commit-tree <tree> -p <parent>`, then publish with `git update-ref <branch> <new> <expected-parent>` CAS. CAS failure is concurrent drift; never reset another writer's ref.
- Direct PR merge is unsafe when the server can atomically bind only head SHA but not the reviewed base SHA. Use a proven merge queue/API with the required preconditions or fail closed.
- PR creation is not safely dispatchable when the hosting API accepts only mutable head/base branch names and offers no atomic precondition binding both reviewed SHAs. Fail closed *before* the network call. Postflight SHA checks can describe an already-created effect but cannot make the mutation itself fail closed.
- If a future API provides atomic reviewed-head/base binding, capture the exact PR identity returned by the successful create response and validate only that PR. On timeout/nonzero exit without a directly returned identity, report `pr_create_outcome_uncertain`; never attribute a concurrently appearing PR from list-set difference or mark the operation passed.
- Keep bounded full stdout for machine-readable JSON parsing separate from redacted/truncated artifact tails. Never parse the artifact tail.
- Completed-effect reconciliation must prove causation, not merely observe that state changed. Commit verification should bind parent, tree, message, and caller re-read HEAD; safe no-op push should be distinguished from a new effect. A unique newly visible remote object is still not causal proof when concurrent actors are outside the local lock.
- Once a commit CAS has published and the commit object is verified, post-commit worktree drift belongs to a concurrent writer. Never restore tracked paths or `git clean` newly untracked paths after publication; preserve the bytes and report a completed-with-warning result. Pre-publication rollback is likewise conditional: restore only state still provably owned by this operation, never blindly overwrite a path whose identity/content changed.
- A hidden or undocumented production CLI flag is not a test capability boundary. Do not leave `--unsafe-*-test-only`, arbitrary shell commands, or generic mutating adapters dispatchable from the production parser. Put unsafe fixture lanes in a separate, non-installed test harness or test internal functions directly; production arguments must reject them before any child executes. Preserve the old security contracts by translating their dependency injection through that harness rather than deleting tests. Keep any harness-only command/environment channel explicitly named, scoped to fixture code, and absent from production environment allowlists.
- Runtime trust pins form a dependency graph: changing a checker changes the loop pin, which changes the loop bytes, which changes the parent dispatcher pin. Update pins leaf-to-root, then regenerate a centralized manifest and run a contract that compares the manifest, every embedded consumer constant, and the actual authenticated bytes. The manifest is an update ledger, not a runtime trust anchor unless its own loader and bytes are independently authenticated.
- Surrounding A→A head checks do not bind evidence collected through a mutable PR number: an A→B→A force-push can return B's checks. Query check-runs and status contexts by the captured immutable commit OID, reject records whose SHA differs, and pin one trusted repository slug through every API loader.
- For network Git mutations, a config denylist checked before `git push` does not close check-to-exec races. Push the immutable source OID from a private bare Git context whose config/HOME are isolated, with a literal destination and exact lease; expose the source object database only as a validated alternate object directory.
- Authenticate authority-bearing helpers before creating or exposing parent-only secrets. Read and hash helper bytes once against an external trust anchor, materialize one private copy, generate the HMAC only afterward, and execute that same copy for both preflight and postflight.
- Network-capable agent runtimes need an isolated private HOME/XDG tree. Copy only the minimum provider auth/config files required for the selected provider, authenticate the executable and its interpreter/dependency closure, and do not expose the caller's general credential stores, SSH agent, or arbitrary PATH.
- Use strict environment allowlists for trusted subprocesses too. Clear shell/Python startup injection (`BASH_ENV`, `ENV`, `ZDOTDIR`, `PYTHONPATH`, `PYTHONHOME`), Git/GitHub ambient selectors, SSH-agent access, parent-only HMACs, and opaque secrets; invoke trusted Python entry points with isolated mode where compatible. Network-capable draft adapters receive only explicit runtime/config variables—not the caller's cloud, registry, GitHub, or custom token environment.
- A parent-only baseline HMAC must be mandatory for every authority-bearing pre/postflight. Missing key or missing MAC fails closed. Every Git child launched while the key exists must use a trusted absolute Git path and a minimal environment that excludes the key and credentials; disable global/system config, fsmonitor, external diff, textconv, and other repository-controlled execution surfaces.
- Resolve linked-worktree state through sanitized Git plumbing (`--git-common-dir` / `--git-path`) rather than assuming `<root>/.git` is a directory. This applies to hooks and merge/rebase/cherry-pick state. If the threat model treats repository hooks as untrusted, preflight must reject existing non-sample hooks as well as snapshot them for postflight tamper detection; a stable malicious hook is not safe merely because it did not change.
- Untrusted verifiers should run with a fresh temporary `HOME` plus a minimal `PATH`/locale/temp environment. A variable denylist is insufficient, and preserving the caller's real `HOME` may expose credential/config files even when token variables are removed.
- A canonical plugin path is not content provenance. Pin authenticated executable/helper content or a trusted commit and revalidate immediately before execution. Pin the executable bytes that form the trust boundary—not volatile release metadata such as `package.json` when it is validated but never executed, because legitimate plugin releases otherwise cause needless fail-closed outages. After changing pins, probe the live canonical installation as well as fixtures. To close same-user TOCTOU fully, execute a verified immutable copy or already-open descriptor rather than re-opening the path.
- Audited plugin copies can still self-resolve back into untrusted working-tree helpers. Set each upstream disable-self-resolve flag, and copy every authenticated sibling the helper sources (for example acknowledgement augmentation helpers) into the private directory. Execute these copies with credential-free environments.
- Apply the same closure rule to bundled relay helpers. A trusted dispatcher must not authenticate only `pr-grind-loop` and then let that private copy reopen a mutable sibling checker. Pin every executed sibling, read and hash its bytes once, build the complete expected private directory layout, and execute only that private bundle. Standalone wrappers should independently authenticate their own children so safety does not depend on always being launched by the parent.
- A marker baseline stored beside untrusted work needs parent-held authentication such as a per-run HMAC. Remove the HMAC key from verifier/agent environments before any repository-controlled command executes.

## Authenticated plugin snapshot recipe

When a trusted entry script sources many sibling files, pinning only the entrypoint digest does not authenticate the execution closure. Prefer a whole-tree snapshot:

1. Pin a reviewed plugin commit in the trusted dispatcher. Treat upgrades as an explicit pin-review event.
2. Use sanitized Git plumbing to archive that exact commit; never archive `HEAD` or copy the mutable working tree.
3. Inspect every archive member before extraction. Reject path traversal, symlinks, hardlinks, devices, and FIFOs.
4. Extract into a private temporary directory, then validate required package identity and required entrypoints *inside the extracted snapshot*.
5. Point all plugin-root variables and script paths at the snapshot. Keep the temporary-directory owner alive until every child and writer invocation finishes.
6. Run local/plugin children with a credential-free allowlist and upstream self-resolution disabled. If a script cannot operate without escaping the snapshot, expand the authenticated closure or fail closed.
7. Regression-test by committing trusted bytes, modifying the working-tree copy to a sentinel payload, materializing the pinned commit, and proving the snapshot still contains only the committed bytes.

This is stronger than checking `git diff --quiet` and then executing a worktree path: cleanliness checks and path re-opens retain same-user TOCTOU windows.

## Required negative regressions

Cover at least:

- worktree-scoped Git config redirects, including a syntactically valid alternate GitHub destination;
- trusted expected-repository mismatch before lock, after lock, and immediately before network mutation;
- remote/config change in the mutation window;
- JSON larger than the artifact-tail limit and over the bounded machine-capture limit;
- concurrent unrelated HEAD movement, including a commit-publish CAS race proving the concurrent commit is never removed; derive the branch ref with `git symbolic-ref HEAD` in fixtures instead of assuming the repository initializes as `main`;
- PR-create fails before network mutation when atomic reviewed-head/base preconditions are unavailable; if a future atomic API is adopted, cover timeout/nonzero uncertainty and prove a concurrently appearing matching PR is never attributed to the invocation;
- optional/canonical base forms and PR retargeting;
- marker creation, removal, symlink, non-regular replacement, and every currently recognized authority artifact;
- baseline tampering, missing key, wrong key, and proof that Git/verifier/agent children cannot observe the parent key;
- linked-worktree common-hook creation/change/removal;
- shell/Python startup injection, SSH-agent inheritance, provider/GitHub/cloud credentials, and arbitrary ambient secrets;
- plugin helper modification, check-to-exec swap, working-tree self-resolution, and missing authenticated sibling helpers.
