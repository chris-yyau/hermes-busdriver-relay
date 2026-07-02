# PR61–PR62 Continuation Lessons

Use when a relay continuation has just merged a skill-sync PR and then needs to refresh `docs/CURRENT_STATUS.md` with the new merged-main evidence.

## What happened

- PR61 synced post-PR60 installed-skill drift back into the repo: updated `references/pr60-skill-sync-delivery-lessons.md` and added durability assertions for full relative reference paths and branch-identity-sensitive finalization lock release.
- Delivery followed the full loop: gated Codex draft, focused/full contract verification, PR-mode Codex lead, independent Grok backstop with `reviewed_diff_hash`, trusted Busdriver PR marker writers, PR creation, post-PR marker cleanup, latest-head PR-grind clean, readiness check, merge, branch cleanup, lock release, and final audit.
- After merge, `docs/CURRENT_STATUS.md` was still stale (PR57 evidence, old SHA, old plugin/test counts), so the next safe slice became a docs-only PR62 refresh.
- The docs refresh first failed its narrow verifier because the draft paraphrased exact evidence wording and used a stale plugin version. The tracked diff was scoped and safe, so Hermes corrected the wording and reran `hermes-busdriver-gate postflight` against the saved baseline until the verifier passed.
- Live final smoke/status evidence showed the installed Busdriver marketplace plugin version as `1.76.1`, even though the earlier planned text said `1.76.0`; docs should use the latest actually observed smoke/status version, not the planned value.
- Tool-call limits interrupted after corrected PR62 postflight, before commit/push/PR/merge. Resume from the dirty docs branch, not from scratch.

## Durable workflow updates

1. **After a skill-sync merge, immediately audit docs/status evidence.** If `docs/CURRENT_STATUS.md` still names an older PR/head/plugin/test count, treat a docs-only refresh as the next safe slice.
2. **Docs refresh verifier should require exact evidence wording.** In particular, guard against paraphrases like `repo status PR61 merge` or `repo skill source synced back installed...`; require the intended full phrases so future readers can grep reliably.
3. **Prefer live observed plugin version over the planned value.** If final smoke/status says `package_version=1.76.1`, update `CURRENT_STATUS` to `1.76.1` even if the original prompt or prior summary said `1.76.0`.
4. **Recover scoped docs drafts with corrected postflight.** If agent-draft postflight fails only because a docs verifier phrase is too strict or the draft paraphrased wording, patch the docs/verifier surgically and rerun `hermes-busdriver-gate postflight` with the saved baseline and exact `--scope-include docs/CURRENT_STATUS.md`.
5. **Do not broaden docs refreshes into authority changes.** Preserve `Still intentionally deferred` and `Operational rule` wording unless the user explicitly requests a policy/ADR slice.
6. **If interrupted after corrected postflight, resume from the dirty docs branch.** Verify the single-file diff, then run commit litmus, commit, deliver verify, PR-mode lead/backstop, PR marker writers, push/PR, PR-grind, readiness, merge, cleanup, and final audit.

## PR62 resume point

At interruption, the repo was on `docs/refresh-current-status-pr61` with only `docs/CURRENT_STATUS.md` modified. Corrected checks had passed:

```text
python3 <current-status-verifier> -> pr62 CURRENT_STATUS verifier passed
git diff --check -- docs/CURRENT_STATUS.md -> pass
hermes-busdriver-gate postflight --baseline-file <Hermes agent-run baseline.json> --scope-include docs/CURRENT_STATUS.md --verifier 'current_status=python3 <current-status-verifier>' -> ok=true
```

Next steps are normal Delivery Mode finalization for PR62; do not rerun PR61.

## Verification pattern

```text
Phase-0 clean main after previous merge
→ branch docs/refresh-current-status-<latest-pr>
→ scoped agent-draft docs-only
→ if verifier wording fails but diff is scoped, patch wording and rerun corrected postflight
→ git diff --check -- docs/CURRENT_STATUS.md
→ focused docs/current-status verifier
→ commit litmus + commit
→ deliver verify with docs verifier (and focused/full tests if claiming fresh reruns)
→ PR-mode Codex lead + independent read-only backstop
→ trusted PR marker writers, push, PR create, post-PR marker cleanup
→ latest-head PR-grind
→ finalization-readiness with raw pr-grind loop payload
→ merge, branch/lock cleanup, final audit
```

## Pitfalls

- Do not document a plugin version from a plan when final smoke/status observed a newer installed plugin version.
- Do not accept paraphrased evidence lines in `CURRENT_STATUS`; exact wording prevents stale-evidence greps from missing drift.
- Do not claim tests/smoke were freshly rerun inside the docs draft unless they actually were; distinguish copied post-merge evidence from newly run verifier checks.
- Do not stop after a corrected postflight if the user asked to continue completing the work; PR62 still needs commit/PR/PR-grind/merge/cleanup.
