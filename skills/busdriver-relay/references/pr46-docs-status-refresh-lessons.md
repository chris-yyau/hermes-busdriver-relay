# PR46 Docs/Status Refresh Lessons

Context: after PR44/PR45 strict helper-evidence fixes and post-merge verification, the relay repo code was clean but status docs still reflected stale PR42-era evidence (`368 passed`, old branch names). The safe continuation slice was a docs/status refresh, not another capability expansion.

## Durable workflow lesson

When the relay non-mutating surface is complete for current policy scope and the user says to continue, prefer a **completion/status refresh** slice if docs lag behind verified repo reality. This keeps downstream agents from planning against stale completion evidence while avoiding unsafe finalization-expansion work.

## What to refresh

Update class-level status docs together, not one file at a time:

- `README.md`: current boundary/status paragraph and helper descriptions.
- `docs/CURRENT_STATUS.md`: implemented surfaces and latest verification block.
- `docs/settling-checks-v2.md`: H1-H13 evidence rows and command notes.

For PR45-style helper-contract work, the docs should explicitly mention:

- `scripts/hermes-busdriver-delivery-status` top-level `read_only: true` envelope marker.
- `scripts/hermes-busdriver-finalization-readiness` strict child envelope validation before using delivery-status evidence:
  - expected child schema;
  - `read_only is True`;
  - `ok` is a boolean;
  - invalid child blocker `delivery_status_schema_invalid`.
- Finalization authority remains false for commit/push/PR/merge/deploy/release/publish/marker-write.

## Verification pattern

Docs-only status refreshes still need full relay verification because stale docs can mislead future agents:

```bash
RELAY_REPO=/path/to/hermes-busdriver-relay
python3 scripts/hermes-busdriver-smoke --repo "$RELAY_REPO"
python3 - <<'PY'
from pathlib import Path
for rel in ['README.md', 'docs/CURRENT_STATUS.md', 'docs/settling-checks-v2.md']:
    text = Path(rel).read_text()
    print(rel, 'delivery_status_schema_invalid' in text, 'read_only: true' in text)
PY
git diff --check
```

Expected smoke shape after PR45/PR46:

```text
ok true
py_compile ok
contract tests 379 passed
main...origin/main clean/synced after merge
```

## Delivery discipline

Even docs-only PRs should follow the same latest-head PR-grind loop:

1. Run local smoke before PR.
2. Open PR with verification evidence.
3. If initial PR-grind reports `blocked` only because checks/reviewers are pending, wait and rerun rather than merging.
4. Merge only after latest-head PR-grind returns clean and finalization-readiness reports `ready_for_merge_handoff` with no blockers.
5. Post-merge, rerun smoke and verify clean synced base.
6. Push a claude-mem observation for the docs/status boundary if claude-mem logging is configured.
