# Blueprint-review arbiter route simplification (subscription fable / inline fallback removal)

When the user asks to simplify Busdriver blueprint-review arbiter routing around “subscription fable”, “inline opus”, “ZenMux fable”, or “subscription fresh opus”, interpret the desired route as:

```text
ZenMux / generic Anthropic-compatible gateway fable
  → fresh subscription opus subagent
  → stop and report an arbitration blocker
```

Remove or avoid documenting these paths for the arbiter:

- subscription `fable` Agent-tool first rung
- inherited/session-model fallback
- inline arbitration by the calling session, including user-authorized inline fallback

Concrete files that carried the contract in this session:

- `skills/blueprint-review/SKILL.md`
- `skills/blueprint-review/scripts/dispatch-gateway-arbiter.sh`
- `docs/adr/0003-fresh-subagent-arbiter-for-blueprint-review.md`

If editing the user’s Claude-side Busdriver setup, remember there may be both a working repo (for example `/Volumes/Work/Projects/busdriver`) and a Claude marketplace clone under `~/.claude/plugins/marketplaces/busdriver`. The user expected the active Claude-side docs/source to be updated too, not just the repo checkout. Inspect installed plugin metadata under `~/.claude/plugins/installed_plugins.json` and/or marketplace metadata before deciding which copy is active.

Verification pattern used successfully:

```bash
bash tests/test-gateway-arbiter-dispatch.sh
bash tests/test-blueprint-review-oracle-arbiter-contract.sh
git diff --check
```

Path casing on macOS mattered for one shell test: running from `/Volumes/Work/Projects/busdriver` matched the test’s `$PWD` expectation, while `/Volumes/work/projects/busdriver` caused the project-local `.claude` deny-rule assertion to fail even though the implementation was unchanged. Prefer the canonical `git rev-parse --show-toplevel` spelling when running these tests.
