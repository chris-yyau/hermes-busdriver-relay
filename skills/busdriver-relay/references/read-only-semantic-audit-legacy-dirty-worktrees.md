# Read-only semantic audit of legacy dirty worktrees

Use this when deciding whether old divergent worktrees contain valid intent worth salvaging, while preserving an explicit no-write boundary.

## Goal and classification

Audit intent, not textual novelty:

- **A — already in current main:** exact, renamed, moved, or evolved/strengthened equivalent.
- **B — obsolete, superseded, historical-only, or unsafe:** do not resurrect.
- **C — valid and missing:** report the exact path and symbol/test/contract; this is the only salvage set.

A `git cherry` or patch-ID miss proves only that the old patch is not exact. It does **not** prove C. Conversely, matching names do not prove semantic equivalence; inspect the current implementation and contract.

## Truly read-only observation

1. Define the audited paths and declare automatic Hermes result-cache telemetry outside those surfaces; create no reviewer scratch.
2. Before worktree-facing Git, inspect repository/common/worktree config, `.git` pointers, attributes sources, and submodule config as plain files.
3. Authenticate the real Git executable. On systems where the public Git path is a tool-selection shim, resolve and authenticate the real binary behind it before sandboxing; otherwise a no-child sandbox correctly blocks the shim's second exec.
4. Run Git under an OS sandbox denying repository writes, network, and child process creation. Also clear ambient `GIT_*`, disable global/system config, set `GIT_OPTIONAL_LOCKS=0`, `GIT_NO_LAZY_FETCH=1`, empty protocols, `core.fsmonitor=false`, and reject any stderr.
5. Capture opening and closing `HEAD`, exact porcelain-v2 status bytes/SHA-256, index SHA-256, and a deterministic worktree manifest. Classify every path with `lstat` before opening it; hash regular-file bytes without following symlinks, record symlinks by link text, and record FIFOs/sockets/devices by type without opening them. Frame sorted manifest fields unambiguously with NUL separators. A status digest alone cannot detect changed bytes whose dirty path set stayed the same.
6. Run no tests, hooks, formatters, package commands, checkout, stash, fetch, or object-producing Git commands when prohibited.

## Audit sequence

1. **Establish topology:** record each HEAD, merge-base/base, branch/upstream state, staged paths, unstaged paths, and untracked paths.
2. **Deduplicate old stacks:** compute stable patch IDs in memory. If stacks match, classify the committed stack once and report the mapping for both worktrees.
3. **Classify each commit's meaningful intent:** use subject, per-commit path set, focused hunks, and current-main history. Separate mechanism from now-invalid capability claims.
4. **Audit dirty state separately:** staged, unstaged, and untracked bytes are distinct evidence. Do not summarize all dirt as one patch.
5. **Map dirty symbols:** extract added top-level functions/tests/constants from dirty diffs and search current main globally. For missing names, look for renamed, moved, or strengthened replacements.
6. **Audit unchanged legacy-only behavior too:** symbol extraction from the dirty diff misses unsafe behavior inherited unchanged from the legacy HEAD. Explicitly compare targeted old tests and their current replacements.
7. **Treat tests as intent evidence, not truth:** an old regression can encode the vulnerability. Common reversal patterns include:
   - automatic stale-lock deletion/reacquisition → fail closed and require explicit recovery;
   - executing helpers from a caller-selected repository → authenticate and execute the tool's own retained bytes;
   - restoring/cleaning hook or post-commit mutations → preserve concurrent/user state and require reconciliation;
   - production smoke for a retired executor → parser rejection plus historical, non-installed fixture coverage.
8. **Reconcile with policy history:** current docs and later policy commits can intentionally retire behavior that still looks well-tested in the old tree.
9. **Report C exactly:** give a literal path/symbol list, including `∅` when empty. Never leave C implicit.
10. **Give archive safety:** when C is empty, say the worktrees are semantically safe to archive/remove only after a forensic bundle captures HEAD/base, index, exact status, staged/unstaged full diffs, untracked bytes/modes, patch-ID mapping, and byte manifests.

## Reporting shape

Keep the parent-agent handoff compact:

- one-line verdict and C count;
- shared committed-stack A/B table when patch IDs match;
- per-worktree dirty A/B/C;
- focused treatment of requested legacy-only tests;
- exact C path/symbol list;
- archive/remove recommendation;
- opening/closing HEAD and status digests, plus zero-drift index/manifest statement;
- tests not run and files created/modified.

## Pitfalls

- **All old commits show `git cherry +`:** this says only “not exact patch-equivalent.” Use semantic history and symbol/contract comparison before calling C.
- **Most added symbols exist in main:** inspect the few missing symbols, but also inspect unchanged inherited legacy tests; either side can contain the only B/C signal.
- **A current file still contains an old helper definition:** search callers. A dead historical helper is not current executable intent.
- **A newer worktree has broader security hardening plus retired routing:** split it into A mechanisms and B capability/policy promotion; do not accept or reject the whole tree as one unit.
- **Closing status matches but bytes drifted:** block the verdict unless the full worktree manifest also matches.
