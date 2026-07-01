# Agent-draft readiness evidence lessons

Session context: while continuing the Hermes Busdriver Relay after the balanced-agent work-plan slice, the user said “繼續” and then “go”. The slice embedded `hermes-busdriver-agent-balance-plan/v0` into `hermes-busdriver-finalization-readiness` as validated advisory handoff evidence, then proceeded through Delivery Mode to PR #43 and merge.

## Durable lessons

- If an `hermes-busdriver-agent-draft` run times out at the Hermes terminal layer, first inspect repo diff, relay run artifacts, and locks before assuming the draft failed. A timed-out wrapper may have left a useful dirty draft plus a live/stale `agent-draft` lock.
- Stale relay locks from a timed-out draft should be released only after verifying there is no still-running matching agent process and the working tree has been reconciled.
- Postflight can fail on ignored cache files produced by verification (`.pytest_cache`, `__pycache__`, `.codegraph/*`) even when tracked files are scoped and tests pass. Clean test-created caches or rerun verification with `PYTHONDONTWRITEBYTECODE=1` and `pytest -p no:cacheprovider`; do not blindly delete unrelated daemon state. For `.codegraph/*`, prefer waiting/stability or report the blocker unless it is clearly test-created noise.
- When embedding one relay helper’s output into another helper, validate it like other nested evidence: exact schema, `read_only is True`, `ok is True`, recursive unsafe authority/execution booleans all false, subprocess nonzero, timeout, malformed JSON, and non-object JSON all fail closed.
- Keep test-side unsafe boolean key lists synchronized with production recursive authority scanning. When production adds new unsafe keys such as `repo_mutation_allowed`, `external_agents_called`, `subprocess_dispatch_called`, `codex_called`, `github_called`, `marker_writes_performed`, or `repo_mutations_performed`, update recursive test assertions too.
- Include newly introduced helper return codes in wrapper exit-code fallback chains. Otherwise subprocess failures/timeouts may collapse to generic exit code `1`, making failures less diagnosable and inconsistent with sibling helpers.
- After a reviewer-fix follow-up commit or approved branch update, previous PR-grind state is stale. Rerun latest-head PR-grind on the new head and fix any current actionable feedback before merge.
- Shell heredoc quoting inside nested `bash -lc` strings is easy to break; for multi-line JSON/Python parsing during delivery, prefer a small Python/execute-code wrapper or write/read a temp file rather than hand-nesting quotes repeatedly.

## Verification pattern from the slice

Use a narrow-to-broad verification sequence:

```text
1. targeted failing/fixed tests for new evidence validation
2. full relevant helper test file
3. focused suite (`test_agent_balance_plan.py`, `test_finalization_readiness.py`, `test_smoke.py`)
4. full `tests/contract`
5. `hermes-busdriver-smoke`
6. gate postflight with ignored-file-stable verification
7. PR-grind latest-head loop after PR creation and after every amend/push
8. post-merge full contract tests + smoke + clean main/open-PR/worktree/lock checks
```

## PR-grind reviewer-fix example

Reviewer bots flagged two valid issues:

- finalization-readiness omitted `agent_balance_plan_rc` from final exit-code fallback;
- tests did not include newly added unsafe authority/execution keys.

Both were fixed before merge, tests reran, the branch was updated, and PR-grind was restarted against the latest head before merging.
