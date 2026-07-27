# OpenCode Busdriver Draft Adapter

> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current authority: [`docs/coding-workflow-authority-map.md`](../../docs/coding-workflow-authority-map.md).

This directory retains the relay-owned OpenCode adapter proof as historical/comparison evidence. It is not an OpenCode plugin installation and OpenCode is not an executor or Busdriver authority.

## Role

OpenCode is not a current executor route. Its historical draft-only **adapter contract** may produce scoped draft changes only in non-installed test harnesses; production parser validation rejects OpenCode before repository, HOME/state, credential, lock, prompt, gate, run-directory, or worker handling.

```text
OpenCode result status = needs_busdriver_review | blocked
commit/push/PR/merge/marker/deploy/release/publish/finalization authority = false
```

The non-installed harness proves the historical adapter mechanics: `--pure`, private HOME/XDG layout, scoped external control directory, bounded result parsing, schema/authority validation, Git reconciliation, and include/exclude scope. The executable test fixture has no production caller, manifest entry, trusted pin, or production authority.

## Files

```text
opencode-result.schema.json    Fail-closed result artifact contract
```

## Historical fixture

`tests/fixtures/opencode/run-opencode-busdriver-draft` is retained as test-only source for the non-installed fixture harness. It is absent from `production_entrypoints` and has no trusted executable pin.

The production parser rejects the removed executor choice:

```bash
scripts/hermes-busdriver-agent-draft --plugin-root <busdriver> --repo <repo> --agent opencode
```

It must fail argparse validation and must not launch OpenCode, copy credentials, or leave a draft diff. Functional `needs_busdriver_review` results are historical fixture evidence only.
