# Pi Busdriver Tool-Harness Adapter

This directory contains the relay-owned Pi adapter. It is not Pi upstream source code.

## Role

Pi is the default target Busdriver-shaped adapter contract. It produces scoped draft changes only in non-installed test harnesses; every production agent/probe blocks immediately after argument parsing—before repository, HOME/state, credential, lock, prompt, gate, run-directory, or worker handling—with `agent_containment_and_credential_broker_unavailable`.

```text
Pi result status = needs_busdriver_review | blocked
commit/push/PR/merge/marker/deploy/release/publish/finalization authority = false
```

## Files

```text
busdriver-tools.ts       Pi extension exposing bd_* tools only
pi-result.schema.json    Fail-closed result artifact contract
```

## Tool boundary

The non-installed harness exercises the extension with built-in tools and unrelated extensions disabled:

```bash
pi \
  --print \
  --no-session \
  --no-approve \
  --system-prompt 'Constrained Busdriver adapter; use only bd_* tools.' \
  --append-system-prompt '' \
  --no-builtin-tools \
  --no-context-files \
  --no-skills \
  --no-prompt-templates \
  --no-themes \
  --no-extensions \
  -e adapters/pi/busdriver-tools.ts \
  --tools bd_status,bd_read,bd_write_draft,bd_bash,bd_artifact \
  --mode json
```

`bd_bash` is argv-only and allowlist-only. Git status/diff forms strip risky Git environment and require `core.fsmonitor=false`, `--no-ext-diff`, and `--no-textconv` where applicable. `bd_read` and `bd_write_draft` refuse trusted marker/state paths, common secret paths, gitignored paths, symlinks, and oversized reads. `bd_write_draft` only writes inside repo root and declared scope, records before/after hashes, and returns draft evidence only.

## Launcher

Both commands below are negative production capability probes and are expected to return blocked:

```bash
scripts/pi/run-pi-busdriver-draft \
  --repo /path/to/repo \
  --prompt-file /path/to/prompt.md \
  --run-dir /path/to/run \
  --scope-include 'src/**'
```

```bash
scripts/hermes-busdriver-agent-draft --agent pi ...
```

They must report `agent_containment_and_credential_broker_unavailable` and must not launch Pi, copy credentials, or leave a draft diff. Functional `needs_busdriver_review` results belong only to the non-installed harness until a future containment and credential-brokering design is implemented and reviewed.
