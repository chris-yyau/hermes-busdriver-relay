# Read-Only Skill-Sync Audit Lessons

Use when the user asks for a read-only audit/planning lane around syncing installed `busdriver-relay` skill references back into the repo source, especially after recent PR merges.

## Workflow

1. **Stay strictly read-only.** Do not edit files, write markers, commit, push, create PRs, or mutate GitHub. If another mutating lane starts while you are auditing, report the resulting WIP as observed state rather than touching it.
2. **Inspect both initial and final worktree state.** A repo can change during a read-only audit. Capture branch, HEAD, dirty status, open PRs, relay lock count, and installed-vs-repo skill diff. If the worktree changes mid-audit, distinguish your reads from someone else’s WIP.
3. **Confirm the selected slice from live drift.** The slice is appropriate when installed skill references or SKILL pointers exist only in the installed Hermes skill or differ from repo source after recent PRs. Prefer this skill-sync slice before a CURRENT_STATUS refresh, because status docs will otherwise become stale again after the skill-sync merge.
4. **Review proposed WIP without owning it.** If a mutating lane has already copied references into the repo, inspect diffs and tests, but do not stage/fix/overwrite. Report exact remaining blockers and recommended checks.
5. **Run only read-only focused validation.** Safe examples: `git status`, `git diff`, `diff -qr`, `gh pr list`, lock status, leakage scans, and focused tests that do not mutate repo state. Label any full suite/smoke/deliver verification not actually run as recommended follow-up.

## Redaction and authority requirements

- Do not copy installed-skill references byte-for-byte into durable repo history until they are sanitized. Installed references often contain session-local paths or raw examples.
- Reject durable references containing private/local path sentinels such as user home paths, raw private temp path examples, or Hermes agent-run cache paths. Prefer symbolic wording like “private-temp example/sentinel” or placeholders.
- Patch installed and repo copies to the same sanitized text before claiming drift clean; otherwise `diff -qr` will recreate the drift immediately after merge.
- Add/keep durability tests that assert full relative reference paths appear in `SKILL.md`, key lesson phrases are present, and private/local path sentinels are absent.
- Preserve fail-closed helper semantics: valid JSON emitted by a helper that exits nonzero may explain the blocker, but must not convert subprocess failure into warning-only success unless the wrapper contract explicitly says so.
- Preserve authority boundaries: a skill-sync/reference/docs slice must not imply new commit/push/PR/merge/deploy/release/publish/marker-write authority, Busdriver marker interop, direct MCP/plugin routing, or Hermes bare-shell gate safety.
- Avoid hard-coded default-base cleanup guidance; use the live PR base branch / saved base branch and its upstream.

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
