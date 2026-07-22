> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Read-Only Skill-Sync Audit Lessons

Use when the user asks for a read-only audit/planning lane around syncing installed `busdriver-relay` skill references back into the repo source, especially after recent PR merges.

## Workflow

1. **Stay strictly read-only.** Do not edit files, write markers, commit, push, create PRs, or mutate GitHub. If another mutating lane starts while you are auditing, report the resulting WIP as observed state rather than touching it.
2. **Inspect both initial and final worktree state.** A repo can change during a read-only audit. Capture branch, HEAD, dirty status, open PRs, relay lock count, and installed-vs-repo skill diff. If the worktree changes mid-audit, distinguish your reads from someone else’s WIP.
3. **Confirm the selected slice from live drift.** The slice is appropriate when installed skill references or SKILL pointers exist only in the installed Hermes skill or differ from repo source after recent PRs. Prefer this skill-sync slice before a CURRENT_STATUS refresh, because status docs will otherwise become stale again after the skill-sync merge.
4. **Review proposed WIP without owning it.** If a mutating lane has already copied references into the repo, inspect diffs and tests, but do not stage/fix/overwrite. Report exact remaining blockers and recommended checks.
5. **Run only read-only focused validation.** Safe examples: `git status`, `git diff`, `diff -qr`, `gh pr list`, lock status, leakage scans, and focused tests that do not mutate repo state. Label any full suite/smoke/deliver verification not actually run as recommended follow-up.
6. **Validate concurrent skill-sync WIP without taking ownership.** If the repo becomes dirty during the audit and the WIP appears to copy installed-only drift into the repo source, it is acceptable to run focused read-only tests against that dirty WIP and report the results as evidence for the proposed slice. Distinguish pre-WIP failures that prove the drift from post-WIP passes that validate someone else's draft; do not stage, fix, or claim authorship.

## Redaction and authority requirements

- Do not copy installed-skill references byte-for-byte into durable repo history until they are sanitized. Installed references often contain session-local paths or raw examples.
- Reject durable references containing private/local path sentinels such as user home paths, raw private temp path examples, or Hermes agent-run cache paths. Prefer symbolic wording like “private-temp example/sentinel” or placeholders.
- Patch installed and repo copies to the same sanitized text before claiming drift clean; otherwise `diff -qr` will recreate the drift immediately after merge.
- Add/keep durability tests that assert full relative reference paths appear in `SKILL.md`, key lesson phrases are present, and private/local path sentinels are absent.
- If delivery uses an added-line redaction/security scan, avoid adding the raw forbidden sentinel strings in new test constants; construct them from smaller pieces so the test still checks the assembled forbidden value without making the scan flag the test itself.
- Preserve fail-closed helper semantics: valid JSON emitted by a helper that exits nonzero may explain the blocker, but must not convert subprocess failure into warning-only success unless the wrapper contract explicitly says so.
- Preserve authority boundaries: a skill-sync/reference/docs slice must not imply new commit/push/PR/merge/deploy/release/publish/marker-write authority, Busdriver marker interop, direct MCP/plugin routing, or Hermes bare-shell gate safety.
- Avoid hard-coded default-base cleanup guidance; use the live PR base branch / saved base branch and its upstream.

- If a read-only audit lane produces a new useful installed-skill reference while a mutating skill-sync slice is in flight, include that sanitized reference in the same repo sync when it is class-level and directly relevant, instead of leaving a known installed-only drift for the next cycle.
- Before declaring a candidate skill-source sync ready, run a final whole-skill installed-vs-repo comparison, not just the target reference diff. If unrelated installed-only drift appears (for example another lesson reference changed during recent docs/status work), classify it as a blocker or explicit scope decision: either sync it with matching durability/redaction tests, or realign the installed copy before claiming drift clean.

## Exact inventory and content-quality review

For a frozen parent→candidate skill-source sync, review the Git objects rather than trusting the live worktree or a test summary:

1. Bind the exact parent, candidate commit, candidate tree, branch, and opening `git status --porcelain=v2 --branch`. Repeat them at close. An upstream/tracking line appearing or disappearing is status drift even when HEAD, tree, and cleanliness are unchanged; report the immutable-tree result separately from the live close-seal blocker.
2. Derive changed paths and modes from the parent→candidate diff. Require the declared file count, add/modify split, scope, and ordinary-file modes; compare every pre-existing reference blob OID with the parent instead of inferring preservation from a shortstat.
3. Reconcile four sets independently: parent reference files, candidate reference files, parent SKILL local-reference paths, and candidate SKILL local-reference paths. Require every candidate file indexed, no dangling local path, and the new catalog block to equal exactly the newly introduced local paths, with unique sorted rows. Keep already-indexed newly added files out of the new-path block.
4. Parse local `references/<name>.md` paths with a boundary that rejects a preceding slash/path token, or parse exact catalog rows. A loose suffix regex will falsely classify external paths such as `skills/orchestrator/references/<name>.md` as missing local skill files. Likewise, distinguish duplicate catalog rows from intentional repeated semantic mentions elsewhere in SKILL.
5. Treat installed-byte equality as provenance only, not content approval. Scan every added blob for UTF-8/nonempty/substantive structure, duplicate or near-duplicate content, balanced Markdown, terminal newline, credential-shaped values, actual user homes, Hermes agent-run paths, and unapproved machine-local roots. Preserve explicitly approved runtime-root conventions; otherwise replace machine-local roots with approved variables or symbolic placeholders even when the installed source contains the same bytes.
6. Classify inert security examples manually after high-confidence scanning; a documented placeholder such as `https://user:secret@host` is not a live credential. Do not let that false positive hide real local-path leakage in another file.
7. Never overwrite a shared repo skill file from the installed copy merely to obtain tree equality. Run the repo's focused policy contracts first; if installed shared text is older or authority-positive, preserve the parent/canonical repo blob and explicitly realign the installed copy only after the reviewed repo candidate merges.
8. When an installed-only reference becomes an in-repo SKILL link, update the repository documentation-policy inventory in the same candidate. Move any newly present path out of `external_or_unavailable_references`, classify retained evolution evidence as historical, and add the conspicuous `HISTORICAL / SUPERSEDED — NON-PRODUCTION` banner plus current authority pointer required by the policy contracts.

## CURRENT_STATUS follow-up after merge

After the skill-sync slice merges, run a separate docs-only/evidence-only CURRENT_STATUS refresh if needed. It should:

- update latest merged PR number, head/merge SHA, plugin version observed during smoke/status, open PR state, relay lock state, installed-vs-repo skill sync, and marker sanity;
- replace stale test counts/timings only with checks actually rerun;
- keep full-suite/smoke/deliver evidence separate from focused read-only audit evidence;
- preserve the intentionally deferred/fail-closed finalization policy wording unchanged.

## Reporting pattern

Report:

- observed current state, including whether WIP appeared during the audit;
- whether the selected next slice is appropriate and why;
- exact redaction/authority requirements for the mutating worker;
- what CURRENT_STATUS should refresh after merge;
- checks actually run, with exact results;
- checks recommended but not run.
