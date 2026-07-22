# Delivery finalization dogfood edge lessons
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Session context: while continuing a relay finalization slice, Hermes staged a Delivery Mode group and ran targeted tests plus Busdriver litmus. The litmus loop found concrete correctness blockers in the delivery/finalization surface before commit.

## Lessons to reuse

- Treat **litmus stdout and process status as a pair**. If `run-review-loop.sh` prints `PASS` but the tool/process reports nonzero, do not treat it as final commit authority. Re-check the marker/freshness and rerun the litmus/status helper until stdout, exit status, and marker evidence agree.
- When `hermes-busdriver-deliver` forwards PR base evidence from `--base`, every wrapper layer must support the flag. If deliver passes `--litmus-base-ref`, `hermes-busdriver-delivery-status` must accept it and forward it to `hermes-busdriver-litmus-status --base-ref`; otherwise `execute push` / `pr-create` fails before reaching the intended operation.
- Hash helper subprocesses used inside finalization checks must be fail-closed. `diff_hash()` / staged-diff helpers should catch `TimeoutExpired` and `OSError` and return unavailable evidence instead of tracebacking and skipping durable blocked artifacts.
- Commit-mode marker summaries must expose enough sanitized evidence for the delivery executor to bind the staged candidate. If the Busdriver commit marker is a 64-hex staged-diff hash, the read-only litmus-status summary should preserve that value as `markers.litmus_passed.diff_hash` while still avoiding raw marker leakage for other formats.
- Before invoking Busdriver trusted writer commands for pre-PR review markers, validate the marker state dir path. Reject empty, absolute, `.`/`..`, repo-escaping, and symlinked state dirs/components (for example a symlinked `.claude`) before running `--write-backstop-verdict` or `--write-pr-marker`.
- When tests evolve after new mutating operations are added, update stale negative tests rather than preserving old assumptions. Example: once `commit` becomes a supported operation, a missing commit message should produce a structured fail-closed artifact, not an argparse “invalid choice” assertion.

## Verification pattern

For this class of finalization-edge fix, run at least:

```bash
python3 -m pytest tests/contract/test_deliver.py tests/contract/test_delivery_status.py tests/contract/test_litmus_status.py -q
```

Then run Busdriver litmus on the exact staged group. If litmus reports blockers, fix them, stage the fixes, rerun the same targeted tests, and rerun litmus. Do not commit until litmus evidence is fresh and internally consistent.
