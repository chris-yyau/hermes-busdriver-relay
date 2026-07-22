# Guarded generic-agent adapters and completion discipline

Use this reference when promoting a generic coding-agent lane (especially OpenCode without a Busdriver-native plugin) or when a long delivery spans tool-call windows.

## Completion discipline

- If the user asked for the whole delivery, a tool-call ceiling is a **checkpoint**, not a new scope boundary. Preserve the task list and resume from the exact unfinished gate on the next continuation.
- Never turn a checkpoint summary into “delivery complete.” State only the verified snapshot and remaining gates.
- Do not repeatedly stop at implementation/test milestones. Continue through frozen snapshot, hash-bound reviews, litmus/pre-PR, gated commit/push/PR, latest-head PR-grind, merge, cleanup, installed-skill/live-status sync, and latest-main verification when those were in scope.
- Earlier green evidence is invalid after any later code, test, policy, docs, manifest, or generated-artifact change. Re-run affected targeted gates and the full frozen-snapshot gates.
- Keep policy-blocked surfaces explicit. “Finish everything” does not authorize inventing Busdriver approval, trusted-marker ownership, or other missing authority.

## Generic guarded adapter promotion checklist

A raw CLI success is not adapter proof. Require all of the following before marking a fallback role programmatically dispatchable:

1. Production routing only through the relay-owned lock + preflight + adapter + postflight envelope.
2. Private HOME/XDG state; copy only required auth material, not ambient plugins/packages/settings.
3. Plugin-free/pure agent mode when supported.
4. A narrowly scoped control-artifact directory. If the agent permission model rejects external artifacts, permit only that per-run directory rather than enabling global external access.
5. Clear stale results before launch and cap untrusted artifact size before parsing.
6. Canonical result JSON template in the prompt.
7. Strict schema and nested/root authority-false validation.
8. Record base and post HEAD; reject HEAD movement.
9. Reconcile actual Git changes against include/exclude scope.
10. Require reported changed files to match actual Git changes exactly.
11. Structured fail-closed results for missing binary, timeout, missing/malformed/oversized artifact, nonzero exit, scope violation, and report/Git mismatch.
12. Fake-binary negative contracts plus one real production smoke with a content verifier.
13. Promotion updates code, role/status metadata, tests, ADRs, README/current status, repo skill, installed skill, and live resolver evidence in the same delivery.
14. `dispatch_allowed=true` means draft dispatch through the verified wrapper only; mutation/finalization/commit/push/PR/merge/marker/deploy/release/publish remain false.

## Useful regression cases

- in-scope edit with matching result;
- out-of-scope and excluded-path edits;
- result lists no file, wrong file, duplicate file, or extra file;
- commit/HEAD movement;
- stale pre-existing result;
- missing and malformed result;
- oversized result;
- timeout and missing executable;
- authority-positive root or nested field;
- private config accidentally copying user packages/plugins;
- model denied access to repo-external control artifacts;
- production launcher routes the lane but preserves finalization=false.
