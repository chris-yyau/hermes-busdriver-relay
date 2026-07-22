# Delivery executor finalization review lessons

Context: during a Hermes Delivery Mode dogfood run for `hermes-busdriver-relay`, a large delivery-executor slice added gated mutating operations (`pre-pr-review`, `commit`, `push`, `pr-create`, `merge`). Busdriver litmus repeatedly stalled in cross-file context collection, so read-only staged-diff backstops (`codex review --uncommitted` plus a leaf staged-diff reviewer) were used to identify finalization blockers before commit.

## Core rule

Mutating Delivery Mode operations must be gated by evidence that is fresh for the exact operation and exact bytes being finalized. Read-only status helpers and historical artifacts must remain default-deny and must never become reusable standing authority.

## Durable lessons

### Commit approval must bind to the current staged diff

A `commit_litmus_fresh` marker that is only newer than `HEAD` is insufficient for standalone Hermes `execute --operation commit`: staged content can change after review without changing `HEAD`.

Required shape:

1. `hermes-busdriver-litmus-status` should preserve recognized 64-hex commit marker content as sanitized metadata, e.g. `markers.litmus_passed.diff_hash`, without exposing raw arbitrary marker text.
2. `hermes-busdriver-deliver execute --operation commit` should:
   - require `decision.status == commit_litmus_fresh`;
   - require `markers.litmus_passed.diff_hash` to be a valid 64-hex hash;
   - recompute the current staged diff hash immediately before `git commit`;
   - fail closed on missing hash, unavailable staged diff hash, or mismatch.
3. Regression tests should cover:
   - happy path commits only when the marker hash matches the staged diff;
   - modifying staged content after review blocks with a staged-diff mismatch;
   - legacy/unbound commit markers block with a missing staged-diff-hash reason.

Use fail-closed reasons such as `commit_litmus_staged_diff_hash_missing`, `staged_diff_hash_unavailable`, and `commit_litmus_staged_diff_mismatch` rather than falling through to `git commit`.

### Hash staged evidence with hardened diff semantics

Do not compute staged evidence with plain `git diff --cached`. In a user repo, plain diff may trigger `diff.external`, textconv, color, or `.gitattributes` diff drivers and can either execute unwanted helper code or hash bytes that do not match sanitized review semantics.

Use a hardened invocation equivalent to:

```bash
git -C "$repo" \
  -c core.attributesFile=/dev/null \
  diff --no-ext-diff --no-textconv --no-color --cached
```

Implementation notes:

- Capture raw bytes, not decoded text, for hash input.
- Strip only trailing newlines before hashing if matching the existing relay `diff_hash` convention.
- Use a scrubbed Git environment (`GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, and no inherited arbitrary `GIT_*`).
- Add tests that monkeypatch subprocess calls and assert `--cached`, `--no-ext-diff`, `--no-textconv`, `--no-color`, and `core.attributesFile=/dev/null` are present and that bytes are hashed without text decoding.

### Requested PR base must flow through every evidence layer

If `deliver --base <branch>` is exposed, forward that base into `delivery-status` and then into `litmus-status --base-ref`; otherwise PR-mode evidence may be computed against default `origin/main`, causing stale/mismatched pre-PR evidence for release/develop bases.

Required shape:

- `hermes-busdriver-deliver --base release/1.0` should pass `--litmus-base-ref origin/release/1.0` to delivery-status.
- `hermes-busdriver-delivery-status --litmus-base-ref origin/release/1.0` should pass `--base-ref origin/release/1.0` to litmus-status.
- Preserve already-qualified refs such as `origin/foo` and `refs/heads/foo`.
- Add wrapper-forwarding tests at both layers.

### Keep finalization lock state separate from Busdriver marker state

Do not reuse `--busdriver-state-dir-name` / marker state (for example `.opencode`) as the Hermes finalization lock root. Marker state controls where Busdriver-style markers live; the finalization lock root controls single-flight mutation. Conflating them lets default-marker and alternate-marker runs acquire different locks for the same repo and mutate concurrently.

Required shape:

- `finalization_state_dir(args)` should use only an explicit Hermes lock-state override such as `--state-dir`.
- A separate helper like `busdriver_marker_state_dir(args)` should provide `.claude` / `.opencode` marker env values to Busdriver trusted writer commands.
- Tests should verify that `busdriver_state_dir_name='.opencode'` does not change the finalization lock root, while an explicit `state_dir='.relay-lock'` does.

### Redact lock tokens inside command diagnostic strings

Redacting dict keys named `token` is not sufficient. Lock helper stdout can contain JSON text like `{"token": "..."}` inside `stdout_tail`; that string may be persisted in run artifacts or printed on release-failure paths while the token is still useful.

Required shape:

- Either omit helper stdout tails from lock command payloads, or redact JSON-style secret fields inside strings before persistence.
- Prefer parsing lock helper payloads from raw stdout before tailing/truncating, then storing only redacted command diagnostics.
- Redaction should catch quoted JSON fields such as `"token": "..."`, `"api_key": "..."`, `"secret": "..."`, `"password": "..."` in addition to CLI args and `key=value` forms.
- Tests should serialize the mutating run envelope and assert the raw token is absent from both structured fields and `stdout_tail` strings.

### Force clean-worktree checks to include untracked files

`git status --porcelain=v1` obeys repo config such as `status.showUntrackedFiles=no`, so untracked files can be hidden. Mutating gates that require clean worktrees (`pre-pr-review`, `push`, `pr-create`, backstop validation, etc.) must force untracked visibility.

Required shape:

```bash
git status --porcelain=v1 --untracked-files=all
```

Add a regression test that sets `status.showUntrackedFiles=no`, creates an untracked file, and verifies `repo_clean()` returns false.

### Scrub Git env before trusting PR-grind / merge evidence

`execute --operation merge` may run a read-only PR-grind loop immediately before `gh pr merge`. That PR-grind evidence is only trustworthy if it was collected against the intended repo/index. Inherited `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, pathspec, trace, or config variables can redirect Git operations inside nested helpers.

Required shape:

- Every subprocess that produces evidence used for mutating `merge` must run with the same scrubbed Git env discipline as `run_safe()` / delivery-status wrappers.
- Add a regression test that sets hostile `GIT_DIR` / `GIT_INDEX_FILE`, monkeypatches the PR-grind subprocess, and asserts those variables are absent from the child env.

### Clean-candidate gates must ignore trusted marker evidence, not all dirt

Busdriver marker files are evidence required for the next delivery step. In repos that do not ignore `.claude/*` / `.opencode/*`, the normal flow can leave marker files untracked. A naive `repo_clean()` gate for `pre-pr-review`, `push`, or `pr-create` will then block the same marker evidence it depends on.

Required shape:

- Keep commit dirty-tree ownership strict: reviewed staged bytes may be committed only when every non-marker unstaged/untracked path is absent or explicitly owned.
- For clean-candidate gates after evidence production (`pre-pr-review`, `push`, `pr-create`, backstop branch-diff validation), ignore only the trusted marker filenames under the configured marker state dir:
  - `litmus-passed.local`
  - `pr-codex-lead.local.json`
  - `pr-backstop-verdict.local.json`
  - `pr-review-passed.local`
- Do **not** ignore arbitrary files or whole state-dir subtrees; parse porcelain paths and allowlist exact marker paths.
- Add tests showing marker files do not block clean-candidate gates, while another untracked file still blocks.

### Convert Hermes backstop wrappers before Busdriver trusted writer calls

Hermes backstop verdicts may use a wrapper schema (`hermes-busdriver-backstop-verdict/v0`) with fields such as `read_only`, `reviewed_repo_root`, and `reviewed_base_ref`. Busdriver `run-review-loop.sh --write-backstop-verdict` accepts a stricter writer payload and rejects unknown top-level fields.

Required shape:

1. Validate the Hermes wrapper first: schema, read-only, independent backstop role, repo root, head, requested base ref, and current branch-diff hash.
2. Convert it before piping to Busdriver's writer:

   ```json
   {"status":"PASS","model":"independent_backstop","issues":[],"reviewed_diff_hash":"..."}
   ```

3. Preserve the validated `reviewed_diff_hash`; do not let the caller supply `diff_hash` / timestamp fields for Busdriver's final artifact.
4. Add tests that capture stdin to `--write-backstop-verdict` and assert the Busdriver payload contains only writer-accepted fields.

### Forward requested PR base into Busdriver PR litmus env

Forwarding `--base` to delivery-status/litmus-status is not enough. When Hermes invokes Busdriver PR-mode `init-review-loop.sh`, `run-review-loop.sh`, `--write-backstop-verdict`, or `--write-pr-marker`, it must set `LITMUS_PR_BASE` to the requested base (for example `release/1.0`) so Busdriver computes Codex/backstop/marker hashes against the same base Hermes later validates.

Important default-base nuance: do **not** give `--base` a parser default of `main`. If the user does not pass a base, leave it unset so delivery-status/litmus-status and Busdriver can resolve the default the Busdriver way (`refs/remotes/origin/HEAD`, falling back to `origin/main`). Only set/pass `LITMUS_PR_BASE` when the caller explicitly supplied a base; when set, pass the same origin-qualified ref used by the validators (for example `origin/release/1.0`) so trusted writer markers and Hermes hash validation are bound to the same diff.

Add tests that cover both explicit and implicit base handling:

- no `--base` ⇒ `run_delivery_status()` does not pass `--litmus-base-ref`, and Busdriver PR-review env does not contain `LITMUS_PR_BASE`;
- `origin/HEAD -> origin/trunk` ⇒ `pr_base_ref(repo, None)` resolves to `origin/trunk`, and live remote freshness checks look up `refs/heads/trunk`;
- explicit `--base release/1.0` ⇒ delivery-status gets `--litmus-base-ref origin/release/1.0` and Busdriver PR review/writer subprocess envs include `LITMUS_PR_BASE=origin/release/1.0` plus the intended marker `BUSDRIVER_STATE_DIR`, while hostile inherited `GIT_*` variables remain stripped.

### Bind GitHub mutations to the verified repository/head

`gh` honors `GH_REPO`; if it leaks into `gh pr create` or `gh pr merge`, Hermes may verify local repo/head evidence but mutate a different GitHub repository. Scrub `GH_REPO` alongside hostile `GIT_*` variables for every subprocess that can contribute evidence or perform a GitHub mutation. Add regression tests that set `GH_REPO=evil/other-repo` and assert child envs do not inherit it.

For `pr-create`, the branch head used by GitHub must be the same remote branch that Hermes compared to local `HEAD`. Either pass an owner-qualified head derived from the verified remote or fail closed for non-`origin` push remotes; do not verify `fork/feature` and then call `gh pr create --head feature` where `gh` may resolve a different branch. Add tests that `--push-remote fork` blocks before `gh_pr_create`.

### Custom marker state dirs must flow into PR hash checks

Clean-candidate gates may allow exact trusted marker files under a configured marker state dir such as `.custom-state`, but branch-diff/backstop hash recomputation can still fail if it hard-codes only `.claude` / `.opencode` as ignored marker roots. Thread `busdriver_marker_state_dir(args)` into `candidate_backstop_diff_hash`, `validate_backstop_verdict_text`, and `pr_review_base_matches`; tests should show a configured marker dir is allowed while arbitrary dirt still blocks.

### Malformed evidence files must return blocked envelopes, not tracebacks

Evidence readers in mutating paths run after lock acquisition. A bad file must produce a structured fail-closed result so the lock can release and the operator sees a JSON envelope.

Required shape:

- Catch both `OSError` and decode errors such as `UnicodeDecodeError` when reading `--backstop-verdict-file`.
- Return a blocked reason like `backstop_verdict_file_unreadable` with side-effect evidence, not a Python traceback.
- Add a regression test using non-UTF-8 bytes.

### Large-slice review sequence

For large finalization slices:

1. Hash-bind the staged diff before review: `git diff --cached --no-ext-diff --no-textconv --no-color | sha256(rstrip_newline)`.
2. Run local compile, targeted tests, full tests, and `deliver verify`.
3. Run independent staged-diff review (`codex review --uncommitted` or a read-only backstop) and treat P1/P2 findings as must-fix before commit.
4. After every must-fix patch, restage, recompute the staged hash, rerun targeted/full verification, and rerun review. Earlier clean review verdicts are stale once the staged hash changes.
5. If Busdriver litmus context collection hangs on a large slice, treat it as a split-slice signal. Do not substitute pytest or a single backstop self-report for required finalization evidence.
6. If tests create a stale Hermes lock in the global relay state, clean the exact lock directory and verify lock status returns `count=0` before continuing; do not leave cleanup for the final audit.

## Common failure modes to check explicitly

- Commit marker fresh by timestamp but not bound to staged bytes.
- Alternate marker state changing the finalization lock root.
- Plain Git diff invoking diff drivers/textconv or respecting hostile Git env/config.
- Custom PR base lost between wrapper layers.
- Lock token present inside nested JSON diagnostic strings.
- Clean-worktree helper hiding untracked files because of repo config.
- Staged diff changed after an async/backstop review verdict.
