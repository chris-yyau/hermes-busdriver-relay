# Delivery executor slice litmus timeout lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Context: during a Hermes Delivery Mode dogfood run for `hermes-busdriver-relay`, an OpenCode adapter slice passed litmus and was committed, then a much larger delivery-executor slice (`scripts/hermes-busdriver-deliver` + `tests/contract/test_deliver.py` + ADR) passed targeted tests but Busdriver litmus repeatedly stalled while collecting cross-file context.

## Durable lessons

- **Do not treat targeted pytest as enough for finalization slices.** A delivery-executor slice can pass `py_compile`, targeted `pytest`, and `git diff --cached --check` but still require independent Busdriver litmus/backstop review before commit/push/PR.
- **Use `git stash push --keep-index --include-untracked` to isolate staged slices.** When a relay worktree contains multiple WIP clusters, preserve the unstaged/untracked remainder before proving a staged-only candidate. This avoids dirty-worktree tests being mistaken for staged-only evidence.
- **If commit-mode litmus hangs in context collection on a large executor/test diff, split smaller instead of only increasing timeouts.** Raising `LITMUS_MAX_WEIGHTED_LINES` and `LITMUS_TIMEOUT` can let the size gate proceed but may still leave smart/docs context collection too expensive. Prefer narrower commits: implementation core, contract tests, ADR/docs, then run litmus per slice.
- **`LITMUS_SKIP_CONTEXT=1` is not a guaranteed full review-context bypass.** It can skip smart context, but other context collection (for example docs context) may still run depending on the live Busdriver scripts. Treat a repeated context-collection timeout as a split-slice signal rather than a pass/fail finding.
- **OpenCode adapter success payloads need the same redaction discipline as blocked/error artifacts.** Validate allowed field shapes, redact accepted payloads before writing/printing, and avoid persisting full untrusted `observed_result`; store bounded metadata such as redacted key names instead.
- **Schema allowlists must be semantic, not just key-based.** If the wrapper allows a key because the JSON schema allows it, validate the corresponding type/enum/shape (`mode`, `tests_run`, `blocked_actions`, tails, lists) before accepting `needs_busdriver_review`.

## Verification pattern

For each isolated slice:

```bash
# Isolate the candidate when other WIP exists
git stash push --keep-index --include-untracked -m 'wip-remainder-before-<slice>'

# Prove staged-only basics
python3 -m py_compile <changed-scripts>
python3 -m pytest <targeted-tests>
git diff --cached --check

# Then run Busdriver litmus/backstop on the staged slice.
# If it times out during context collection, split the slice further.
```

After the slice is committed, restore the remainder and continue in the next small slice. Do not claim `deliver-pr` readiness until every slice has passed litmus/backstop, the full suite has passed on the recombined branch, and Delivery Mode evidence is fresh.
