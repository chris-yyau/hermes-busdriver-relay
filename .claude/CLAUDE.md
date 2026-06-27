# Hermes Busdriver Relay — Project Guide

Private **Hermes-side** relay for the user's Busdriver / Claude Code workflow.
This repo holds **Hermes-owned integration artifacts only** — it is not a Busdriver
clone and must not vendor Claude plugins, MCP configs, runtime markers, credentials,
or Busdriver skill bodies.

> This file lives at `.claude/CLAUDE.md` (helmet's standard project-guide location).
> `.gitignore` does **not** blanket-ignore `.claude/`; it ignores only specific
> runtime/gate state inside it (`.claude/*.log`, `litmus-state.md`, `bypass-log.jsonl`,
> `_backstop/`, `worktrees/`, …). Everything else under `.claude/` — including this
> file — stays tracked, so the Hermes agent loads it on a fresh clone.

## Boundary (read this first)

```text
Hermes            = intake, Phase 0 discovery, JIT source reads, read-only status, notification
Busdriver / Claude Code = workflow authority, gates, reviews, MCP/plugin routing, execution,
                          commits, PRs, merges
```

- **Busdriver is a read-only reference, never a dependency to copy.** Source is read
  during Phase 0 discovery at `/Volumes/work/projects/busdriver` (and the installed
  marketplace plugin at `~/.claude/plugins/marketplaces/busdriver` for smoke). Read it;
  do **not** vendor or duplicate its plugins, MCP configs, runtime markers, credentials,
  or skill bodies into this repo.
- Busdriver gates are largely Claude Code **hook-runtime** behavior. A Hermes bare shell
  running a Busdriver script does **not** automatically fire those hooks — so Hermes shell
  execution is **not** Busdriver-gate-safe, and must never claim to be.

## Tech stack

- **Python 3** standard library only. Source files are the executable, extension-less
  scripts under `scripts/` (run as subprocesses, not imported as a package).
- **pytest** for contract tests under `tests/contract/`. Config in `pyproject.toml`
  (`testpaths = ["tests"]`, `python_files = ["test_*.py"]`).
- No third-party runtime dependencies.

## Layout

```text
.claude/CLAUDE.md                           This guide (tracked via gitignore exception)
README.md                                   Full command reference + boundary
ADRs/                                        Architecture decisions (0001–0004)
docs/CURRENT_STATUS.md                       Completion / verification state (source of truth)
docs/hermes-busdriver-integration-contract-v2.md
docs/settling-checks-v1.md, -v2.md           H1–H13 status maps
skills/busdriver-relay/SKILL.md              Hermes skill source
skills/busdriver-relay/references/*.md       Skill reference notes
scripts/hermes-busdriver-*                   Read-only probes, lock, gate, draft launcher, delivery tooling
tests/contract/test_*.py                     Contract tests (invoke scripts as subprocesses)
```

## Scripts (all under `scripts/`)

| Script | Role | Mutates? |
|--------|------|----------|
| `hermes-busdriver-status` | Busdriver root/config/hook/route/marker/lock + repo health probe | read-only |
| `hermes-busdriver-lock` | Hermes-owned single-flight lock (`~/.hermes/busdriver-relay/locks`) | lock state only |
| `hermes-busdriver-runtime-check` | H13 hook-runtime equivalence checker | read-only |
| `hermes-busdriver-gate` | Equivalent `preflight`/`postflight` gate runner (baseline diff, scope, verifiers) | baseline file only |
| `hermes-busdriver-agent-draft` | Generic draft agent launcher (Codex only today) | working-tree diff, no commit |
| `hermes-busdriver-agent-smoke` | Optional real-agent adapter smoke (consumes quota) | throwaway temp repo |
| `hermes-busdriver-delivery-status` | Read-only Delivery Mode status envelope | read-only |
| `hermes-busdriver-deliver` | Fail-closed Delivery Mode dispatcher skeleton (plan/status only) | read-only |
| `hermes-busdriver-pr-grind-check` | Read-only PR-grind readiness checker (`clean`/`wait`/`needs_fix`/`blocked`) | read-only |
| `hermes-busdriver-smoke` | Safe smoke runner | read-only |

See `README.md` for the full invocation flags for each.

## Testing

```bash
# Active Python here lacks pytest; use uvx (the smoke runner does this fallback too):
uvx --from pytest pytest tests/contract -q

# If pytest is on PATH / in a venv:
pytest -q
```

- Tests are **contract tests**: they launch the `scripts/` via `subprocess` and assert
  on JSON output + exit codes. Because the code under test runs in a subprocess, ordinary
  `pytest-cov` line coverage does **not** trace it — meaningful coverage would need
  `coverage` subprocess plumbing. Treat the contract assertions, not a coverage %, as the
  signal. (Last verified: 110 passed.)
- `tests/contract/test_gate.py` is the gold-standard pattern (tmp git repo + fake busdriver
  plugin fixtures). Copy its structure for new script tests.

## Conventions & invariants

- **Fail-closed, read-only by default.** Probes and checkers never write `.claude/`,
  `.opencode/`, the Busdriver source, or the target repo.
- Draft launchers stop at `status=needs_busdriver_review`. They may leave a working-tree
  diff but keep `commit_allowed`, `push_allowed`, `pr_allowed`, `merge_allowed`,
  `deploy_allowed` **false**.
- **Delivery Mode finalization** (branch/commit/PR/merge) happens only on explicit user
  request, and only through a litmus/pre-PR-equivalent check before commit/PR plus a
  pr-grind-equivalent loop before merge (status rollup, bounded wait for reviewer bots,
  address actionable comments, merge only when clean).
- After merge, **sync the PR base branch discovered from PR status** — do not hardcode `main`.
- Hermes-owned state (locks, gate baselines, agent runs) lives under `~/.hermes/busdriver-relay/`,
  never inside `.claude/` or the target repo.
- GitHub issue/comment mutation is a separate side effect requiring explicit user request.

## Still intentionally deferred (blocked by design, not missing work)

`hermes-busdriver-deliver` execute mode · repo-mutating Codex launcher finalization ·
`hermes-busdriver-codex-goal` with commit authority · `.claude/hermes/jobs` queue ·
commit/PR/merge automation inside draft launchers · deploy/release/publish automation ·
direct MCP/plugin routing · any claim that Hermes bare-shell execution is gate-safe.

## CI

This is a **public** repo (`chris-yyau/hermes-busdriver-relay`) running the full helmet
pipeline. CI lives in `.github/workflows/` (tracked):

- **`tests.yml`** — `test` job runs the contract suite (`pytest tests/contract`) on push/PR;
  push-only `compliance` job emits an SBOM (Syft) + Trivy license/vuln scans. **Codecov is
  N/A by design** — subprocess contract tests aren't line-traced, so the contract assertions
  are the signal, not a coverage %.
- **`security.yml`** — backstop scanners on push/PR: Semgrep (Code security), Checkov
  (IaC misconfig), Zizmor + SHA-pin check (Actions security), Trivy (Dependency CVEs). A
  `changes` job gates them so they skip cleanly on irrelevant PRs (skipped = passing).
- **`scorecard.yml`** — weekly OpenSSF Scorecard (`publish_results: true`).
- **`pinact.yml`** — auto-pins actions to full SHA on push to `main`.
- **`dependabot.yml`** + **`dependabot-auto-merge.yml`** — weekly github-actions + pip
  updates; safe bumps auto-approved/merged (repo is opted in via `vars.DEPENDABOT_AUTO_APPROVE`).

Repo is configured for squash-only merge + auto-merge + delete-on-merge, `selected` Actions
with SHA-pinning required. **Required status checks** are tracked in
`.github/required-checks.lock`; `scripts/check-required-checks.sh` detects drift (lock vs
workflow source, lock vs branch protection). Run it before any branch-protection or job-rename
change. Branch protection uses `enforce_admins: false` (solo-dev escape hatch) — flip to `true`
when a second maintainer gets write access.

All workflow actions are SHA-pinned (`.github/scripts/check-pinned-uses.sh` enforces it; the
Zizmor job re-checks in CI).

## Authoritative references

- `README.md` — full command reference and boundary statement.
- `docs/CURRENT_STATUS.md` — current scope, verification commands, last verified results.
- `ADRs/` — why decisions were made (repo boundary, hook-runtime equivalence, gate runner,
  draft launcher).
