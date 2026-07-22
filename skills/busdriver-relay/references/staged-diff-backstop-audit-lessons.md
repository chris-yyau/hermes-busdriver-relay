# Staged-diff backstop audit lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use these lessons when the user asks for an independent, read-only backstop review of a staged relay diff, especially when the worktree is dirty or finalization authority is in scope.

## Durable lessons

1. **Review the staged index, not the dirty worktree story.** Capture `git diff --cached --name-status`, `git diff --cached --stat`, and the exact cached diff hash before drawing conclusions. If unstaged changes contain the sensitive implementation while staged docs/tests claim it, fail closed: the proposed commit is internally inconsistent even if the dirty worktree tests pass.

2. **Hash-bind the verdict early and re-check it at the end.** For the requested verdict, compute `sha256(git diff --cached --no-ext-diff --no-textconv --no-color)` after rstripping only trailing newlines. Also record `git rev-parse HEAD` and the base ref. Before final JSON, recompute `git diff --cached --name-status` and the hash: staged content can change mid-review (for example a fourth file gets staged after an initial three-file snapshot). The final `reviewed_diff_hash` must bind to the current staged diff actually reviewed, and the summary should explicitly note any staged-file/hash drift observed during the review. If the hash or HEAD cannot be inspected/preserved, the review verdict must be `passed=false`.

3. **Review every currently staged file, not just the originally named focus files.** If the user names focus surfaces but asks for the staged diff, include all paths in the final cached diff in scope. A small extra staged docs/test/reference update is still part of the candidate hash and can affect durability or assertions.

4. **Dirty-worktree tests are evidence, not staged-only proof.** A targeted pytest run in a dirty checkout can be useful for finding regressions, but do not cite it as proof that the staged diff passes. Either run from a clean/index-applied worktree or clearly mark the caveat.

4. **Partial staging is a finalization-authority blocker.** For busdriver relay slices, docs/status/tests/skills and implementation must move together. Claims such as `gated_delivery_mode_executor` or OpenCode adapter proof are unsafe if `scripts/hermes-busdriver-deliver`, finalization status/readiness helpers, or contract tests are unstaged.

5. **OpenCode/agent artifacts are untrusted egress surfaces.** When reviewing adapter scaffolds, inspect every path that writes stdout/stderr tails, invalid observed payloads, final reports, or nested artifacts. Require redaction before persistence/emission and sentinel tests for token/API-key forms.

## Minimal read-only audit sequence

```bash
git rev-parse --show-toplevel
git rev-parse HEAD
git diff --cached --name-status
git diff --cached --stat
python3 - <<'PY'
import hashlib, subprocess
p = subprocess.run([
  'git','diff','--cached','--no-ext-diff','--no-textconv','--no-color'
], stdout=subprocess.PIPE, check=True)
print(hashlib.sha256(p.stdout.rstrip(b'\n')).hexdigest())
PY
git diff --name-status
git ls-files --others --exclude-standard
git diff --cached --check
```

If tests are run while unstaged changes exist, report that explicitly and keep the verdict fail-closed unless staged-only inspection is sufficient.
