# Relay v1 Settling Checks

This file maps the Ultra Council H1-H13 checklist to what this repository currently implements.

## Current scope

Relay v1 is **read-only + lock/status only**. It does not launch Codex, commit, push, create PRs, merge, deploy, or call MCP/plugin tools.

## Checks

| Check | v1 status | Evidence |
|---|---|---|
| H1 standalone dispatcher check | Deferred | Mutating launcher is not implemented. |
| H2 final result envelope/schema | Deferred | Mutating launcher is not implemented. |
| H3 dirty tree fail-closed | Status-only | `hermes-busdriver-status` reports dirty tree; no mutation path exists. |
| H4 scope containment | Deferred | Requires mutating launcher. |
| H5 gate bypass check | Pass by absence | Relay v1 has no commit/PR/merge/deploy code path. |
| H6 read-only status check | Implemented | `tests/contract/test_status_probe.py` snapshots fake Busdriver tree before/after. |
| H7 drift invalidation | Partial | Status reports critical file hashes, including `ultra-oracle` scripts/config; no launcher exists to disable yet. |
| H8 state-dir/plugin-root portability | Partial | Status accepts `--plugin-root`, `--state-dir`, `--user-config`; live smoke uses real Busdriver. |
| H9 marker freshness | Status-only | Status reports active markers with mtime/age/preview, including `skip-ultra-oracle.local` and `ultra-oracle/`; does not validate freshness as approval. |
| H10 concurrency | Implemented scaffolding | `hermes-busdriver-lock` acquire/status/release under Hermes-owned state. |
| H11 external side effects | Pass by absence | Relay v1 performs no external mutation. |
| H12 sensitive payload | Pass by absence | Relay v1 sends no advisory/model payload. |
| H13 hook-runtime equivalence | Deferred | No mutating launcher until this is proven. |

## Commands

```bash
scripts/hermes-busdriver-smoke \
  --plugin-root /path/to/busdriver \
  --repo /path/to/project \
  --pretty
```

```bash
scripts/hermes-busdriver-status \
  --plugin-root /path/to/busdriver \
  --repo /path/to/project \
  --pretty
```

```bash
scripts/hermes-busdriver-lock acquire --repo /path/to/project --operation repo-mutation
scripts/hermes-busdriver-lock status --pretty
scripts/hermes-busdriver-lock release --repo /path/to/project --operation repo-mutation --token <token>
```

## Not yet allowed

- `hermes-busdriver-codex-goal`
- queue inside `.claude/`
- direct MCP/plugin calls
- direct repo mutation from Hermes
- any claim that Hermes shell execution is Busdriver-gate-safe
