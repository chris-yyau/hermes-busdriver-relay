# Staged-diff backstop drift and finalization-test lessons

Use these lessons when performing an independent read-only backstop review of a staged `hermes-busdriver-relay` diff, especially for finalization surfaces where another worker may restage or narrow the candidate while the review is in progress.

## Durable lessons

1. **Treat staged hash drift as a blocking review result, not a bookkeeping note.** If the requested/reported staged hash differs from the first observed hash, or if the staged file set/hash changes before finalizing, do not return PASS for the earlier candidate. Re-bind the verdict to the final `git diff --cached --no-ext-diff --no-textconv --no-color` hash and explicitly report the drift.

2. **Re-check staged file set at the end, even after tests pass.** A test run can take long enough for a sibling worker or operator to restage a smaller candidate. The final review scope is the current index, not the initial snapshot. If the index shrank from a multi-file implementation/test/docs candidate to only a subset, review and verdict must reflect the subset and call out that earlier files are no longer covered.

3. **Use scoped Git signing overrides for read-only contract tests that create temp commits.** On machines with global commit signing enabled, pytest fixtures that initialize temp repos may fail on passphrase prompts even though the product code is fine. For review-only verification, rerun with scoped environment overrides rather than mutating repo/global config:

```bash
GIT_CONFIG_COUNT=2 \
GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=false \
GIT_CONFIG_KEY_1=tag.gpgsign GIT_CONFIG_VALUE_1=false \
python3 -m pytest tests/contract/test_deliver.py tests/contract/test_delivery_status.py tests/contract/test_litmus_status.py -q
```

Report the initial setup-sensitive failure as a caveat, but do not make it a product blocker if the scoped rerun passes.

4. **For mutating finalization executor reviews, test coverage absence can itself be blocking.** If a staged diff exposes commit/push/PR/merge/pre-PR-review operations, require focused tests for the exact safety gates: staged-diff hash match/mismatch, safe backstop verdict file reading, Busdriver writer payload conversion, push lease/ancestor/non-origin behavior, owner-qualified PR heads and `GH_REPO` scrubbing, merge PR-grind recursive authority rejection, lock release failure reconciliation, and custom marker-state-dir/symlink handling.

5. **Probe child-envelope recursive authority directly when reviewing.** A helper that validates only `decision` fields can still accept top-level or nested `*_allowed=true` in a PR-grind/litmus/backstop envelope. In read-only review, import or run the validator against a minimal payload with top-level and nested authority-positive fields; if it returns safe, block until recursive false-authority tests and implementation exist.

## Minimal read-only sequence additions

After the standard staged-diff audit sequence:

```bash
# Run tests with scoped signing override if fixtures create commits.
GIT_CONFIG_COUNT=2 \
GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=false \
GIT_CONFIG_KEY_1=tag.gpgsign GIT_CONFIG_VALUE_1=false \
python3 -m pytest tests/contract/test_deliver.py tests/contract/test_delivery_status.py tests/contract/test_litmus_status.py -q

# Re-bind final verdict to the current index after tests.
git diff --cached --name-status
python3 - <<'PY'
import hashlib, subprocess
p = subprocess.run(['git','diff','--cached','--no-ext-diff','--no-textconv','--no-color'], stdout=subprocess.PIPE, check=True)
print(hashlib.sha256(p.stdout.rstrip(b'\n')).hexdigest())
PY
```

If the final hash/file set differs from the start, return a blocker unless the user explicitly asked to review the new smaller hash and you have reviewed every currently staged file.
