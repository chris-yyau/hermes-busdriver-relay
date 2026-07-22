# Finalization review-loop and delivery hardening pitfalls
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when finishing Hermes/Busdriver relay delivery slices under Busdriver commit/PR gates.

## Do not misattribute platform/tool limits to the user

If Hermes is forced to stop because the runtime says the maximum tool-calling iterations were reached, report it as a platform/runtime limit. Do **not** say the user instructed you to stop. If the user later says to continue, immediately resume from the checkpoint with tools.

## Fresh review evidence must bind to the current staged diff

- Record the staged diff hash immediately before dispatching or running a review.
- If any file is patched, restaged, stashed/applied, or otherwise changes the staged set, the previous PASS no longer certifies the candidate.
- Recompute the staged diff hash and rerun commit/PR review evidence before Delivery Mode commit/push/PR.

## Busdriver `run-review-loop.sh` context collection can stall

Symptom: output stays at `Collecting cross-file context...` while `run-review-loop.sh` consumes CPU.

Safe recovery:
1. Confirm the process belongs to the target worktree, then kill only that worktree-owned review-loop process.
2. Re-run review with context guards, for example:
   ```bash
   BUSDRIVER_PLUGIN_ROOT="$HOME/.claude/plugins/marketplaces/busdriver" \
   CLAUDE_PLUGIN_ROOT="$HOME/.claude/plugins/marketplaces/busdriver" \
   LITMUS_SKIP_CONTEXT=1 \
   LITMUS_CONTEXT_TIMEOUT=1 \
   LITMUS_MAX_CONTEXT_DIFF_BYTES=1 \
   LITMUS_DOCS_CONTEXT=0 \
   LITMUS_TIMEOUT=1800 \
   bash "$HOME/.claude/plugins/marketplaces/busdriver/skills/litmus/scripts/run-review-loop.sh"
   ```
3. If the loop still stalls before review, inspect the Busdriver smart/docs-context scripts or use an equivalent fresh review path, but do not proceed to Delivery Mode commit without a fresh marker/hash accepted by the gate.

## Large-diff review-loop prompt workaround

If `run-review-loop.sh` burns CPU in Bash before the review CLI starts, the bottleneck can be shell parameter substitution with a huge `{{STAGED_DIFF}}` prompt. This can happen **after** `Collecting cross-file context...` even when `LITMUS_SKIP_CONTEXT=1`, because the expensive step may be Bash `${PROMPT/.../$STAGED_DIFF}` placeholder replacement rather than smart-context collection.

Safe workarounds, in preference order:
1. Rewrite the local `.claude/litmus-state.md` prompt for that iteration so it does **not** embed the full diff; instead instruct the read-only reviewer to inspect `git diff --cached -- <touched files>` itself and include the current staged diff hash in the prompt. Keep SAST/iteration placeholders intact if useful, then rerun the loop.
2. If you must preserve the exact full-diff prompt, create a **temporary, non-repo** copy of `run-review-loop.sh` that keeps `SCRIPT_DIR` pointed at the real Busdriver scripts but performs placeholder substitution via Python `str.replace` over temp files, not Bash parameter substitution. Use it only for the current review run and delete/ignore it afterward; do not commit the workaround into the target repo.
3. Do not treat targeted pytest/full contract as a substitute for review evidence. The Delivery Mode commit still needs fresh review evidence bound to the staged hash and a marker/hash accepted by the gate.

### Commit-mode raw-line ceiling has no override

Busdriver commit-mode review has a hard raw total-line ceiling (observed at `ADDITION_LINES + DELETION_LINES > 2000`) separate from weighted-line and staged-file overrides. `LITMUS_MAX_WEIGHTED_LINES` does **not** raise this ceiling. If a candidate is barely over the raw ceiling:

1. Save the complete staged patch before changing the index.
2. Split into logical commits that each stay below the raw ceiling.
3. Keep each split commit buildable/green: include the minimal coupling tests or reference assertions needed for that slice, even if the larger remainder is stashed.
4. Use `git stash push --keep-index` only after staging the first slice; then verify the staged slice and check that the stash does not become the only copy of later test/skill updates.
5. Recompute the staged hash and rerun Busdriver review for each slice. A review PASS for the pre-split hash does not certify any split commit.

## Finalization trust-boundary checklist for delivery tools

When a Busdriver/Hermes delivery helper crosses from review evidence into mutation, check these before commit/push/PR:

- Backstop verdict files: repo-confined, no symlink components, regular file only, bounded size/read, UTF-8 decode fail-closed, and require `reviewed_diff_hash` rather than accepting caller-supplied aliases.
- Commit after staged-hash check: preserve the repo's normal hook runtime for Delivery Mode commits unless the user explicitly authorizes a different trust model. Use real `git commit` with a scoped signing override when needed (for example `git -c commit.gpgsign=false commit --cleanup=verbatim -m ...`), then verify that the side effect matches the reviewed candidate: parent is the exact pre-commit HEAD, commit tree equals the reviewed staged tree, message equals the requested message, and any hook-created drift is reconciled fail-closed. Do **not** use `--no-verify`, `commit-tree`, or direct `update-ref` as the normal path in hook-preserving slices; direct ref updates are only rollback/reconciliation internals after a completed side effect has been detected and must still be old/new-SHA guarded.
- Untracked baseline hygiene: do not fingerprint every untracked file in the repo before commit. Scope pre-existing-untracked protection to paths that can affect reviewed-data safety (for example reviewed deletion/replacement paths and allowed marker evidence), and treat unrelated large/unignored artifacts as outside the commit candidate rather than permanently blocking the mutation. Keep the fail-closed behavior for a pre-existing untracked file at a reviewed deletion path: it may be user data and must not be cleaned by hook-drift reconciliation.
- Rollback of reviewed deletions: do not run one blanket `git restore --source <expected_tree> --staged --worktree -- <all reviewed_paths>` when the reviewed set includes paths staged for deletion; a deleted path is not present in the expected tree and can make restore abort. Split restore/reconcile by path class: restore index/worktree for paths present in the expected tree, and explicitly remove/clean reviewed deletion paths that hooks recreated, while leaving non-reviewed dirty/untracked paths untouched and fail-closed.
- Commit gate hygiene: explicitly block staged Busdriver marker/evidence files before committing. Keep the staged-marker denylist in parity with delivery-status marker discovery, not only the files recently touched in a review. At minimum cover `.claude`, `.opencode`, and any configured marker state dir for local markers such as `freeze.local`, `careful.local`, `design-review-needed.local.md`, `skip-litmus.local`, `litmus-passed.local`, `pr-codex-lead.local.json`, `pr-backstop-verdict.local.json`, `pr-review-passed.local`, and `pr-grind-clean.local`. Allow marker files as untracked/modified evidence for subsequent gates, but never include them in the commit object.
- Subprocess timeout safety: side-effecting helper launches (including Busdriver trusted writers such as `run-review-loop.sh --write-backstop-verdict`) must run in their own process group/session and kill the whole group on timeout. Avoid raw `subprocess.run(..., timeout=...)` for commands that may spawn grandchildren.
- Git/GH environment: scrub inherited `GH_REPO`, `GH_HOST`, dangerous `GIT_*`, and shell startup env (`BASH_ENV`, `ENV`, `ZDOTDIR`); only add explicit safe `GH_REPO` for verified GitHub slug calls. Use the same hardened Git env for remote-head validation and push so the check and mutation cannot target different repos. Dirty-tree classification commands must also be hardened in *both parent and nested helpers*: inject `-c core.fsmonitor=false` into `git status`/generic git helpers and disable global/system Git config so a repo-local fsmonitor hook cannot execute during pre-mutation gates.
- GitHub remote parsing: read the raw local remote URL (`git config --local --get-all remote.<name>.url`) rather than `git remote get-url`, because `get-url` can expand `url.*.insteadOf` rewrites. Require exactly one raw URL and accept only anchored GitHub origin URL forms.
- Push and PR-create remote validation: always use `--force-with-lease` for push, including missing-remote-branch creation (`refs/heads/<branch>:`). Reject configured `remote.<name>.pushurl` plus local `url.*.pushInsteadOf` **and** `url.*.insteadOf` before validating, pushing, or doing PR-create remote-head lookups; both rewrite forms can make the reviewed remote/head check and the GitHub mutation target diverge.
- PR/pre-PR base propagation: if Delivery Mode accepts a non-default `--base`, propagate that base all the way through the nested delivery-status and litmus-status helpers (`--litmus-base-ref` → `hermes-busdriver-litmus-status --base-ref`). Otherwise pre-PR evidence may be generated for one base while post-lock status observes another, causing either unsafe mismatch or spurious `pr_review_base_mismatch` blocks. When hardening a parent gate, inspect the nested helper interface in the same slice; parent-only forwarding can reintroduce argparse failures or split-brain evidence.
- PR head/base: default `--head` to `owner:current-branch` derived from the verified origin owner, and bind omitted `--base` to the observed/reviewed base.
- PR-grind/loop output: recursively reject nested authority flags (`commit_allowed`, `push_allowed`, `merge_allowed`, etc.) set true, not just top-level flags.

## Verification sequence after fixing review findings

1. Add failing contract tests for each review finding first.
2. Patch implementation.
3. Run targeted contract tests for touched surfaces.
4. Run full `tests/contract` with scoped signing override if the host has global commit signing enabled:
   ```bash
   GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=false \
   python3 -m pytest tests/contract -q
   ```
5. Recompute staged diff hash.
6. Re-run fresh Busdriver review until PASS before Delivery Mode commit.
