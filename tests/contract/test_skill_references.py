from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "busdriver-relay" / "SKILL.md"
REFERENCE_DIR = ROOT / "skills" / "busdriver-relay" / "references"
REFERENCE = REFERENCE_DIR / "june-2026-pr-reviewer-quality-evaluation.md"
CONTINUATION_REFERENCE = REFERENCE_DIR / "continuation-subagent-dispatch-lessons.md"
PR49_TO_PR52_REFERENCES = {
    "pr49-skill-sync-delivery-lessons.md": "Finalization-readiness expects the raw PR-grind loop payload",
    "pr50-docs-status-refresh-lessons.md": "Preserve policy guardrails verbatim",
    "pr51-finalization-unlock-adr-lessons.md": "must keep authority false",
    "pr52-adr0006-contract-status-lessons.md": "Preserve compatibility fields like `contract_adr`",
}
PR53_TO_PR55_REFERENCE = REFERENCE_DIR / "pr53-pr55-skill-sync-lessons.md"
PR56_REFERENCE = REFERENCE_DIR / "pr56-skill-sync-delivery-lessons.md"
CURRENT_STATUS_READONLY_REVIEW_REFERENCE = REFERENCE_DIR / "current-status-readonly-review-lessons.md"
RELAY_COMPLETION_SWEEP_REFERENCE = REFERENCE_DIR / "relay-completion-sweep-lessons.md"
PR60_REFERENCE = REFERENCE_DIR / "pr60-skill-sync-delivery-lessons.md"
PR61_TO_PR62_REFERENCE = REFERENCE_DIR / "pr61-pr62-continuation-lessons.md"
PR63_TO_PR64_REFERENCE = REFERENCE_DIR / "pr63-pr64-skill-sync-redaction-lessons.md"
PR66_REFERENCE = REFERENCE_DIR / "pr66-current-status-refresh-lessons.md"
PR67_REFERENCE = REFERENCE_DIR / "pr67-skill-sync-review-fix-lessons.md"
PR68_REFERENCE = REFERENCE_DIR / "pr68-late-async-test-followup-lessons.md"
READ_ONLY_SKILL_SYNC_AUDIT_REFERENCE = REFERENCE_DIR / "read-only-skill-sync-audit-lessons.md"
IDLE_CLEAN_FINALIZATION_READINESS_REFERENCE = REFERENCE_DIR / "idle-clean-finalization-readiness-lessons.md"
IDLE_FINALIZATION_READINESS_STATUS_AUDIT_REFERENCE = REFERENCE_DIR / "idle-finalization-readiness-status-audit-lessons.md"
SKILL_SYNC_CURRENT_STATUS_CONVERGENCE_REFERENCE = REFERENCE_DIR / "skill-sync-current-status-convergence-lessons.md"
RELAY_ROUTER_AGENT_ROLE_SPLIT_REFERENCE = REFERENCE_DIR / "relay-router-agent-role-split.md"
RELAY_ROUTER_ROLE_POLICY_REFERENCE = REFERENCE_DIR / "relay-router-role-policy-2026-07.md"
SKILL_SYNC_PR75_ROUTER_ROLE_REFERENCE = REFERENCE_DIR / "skill-sync-pr75-router-role-lessons.md"
PR78_SKILL_SYNC_PRE_PR_REFERENCE = REFERENCE_DIR / "pr78-skill-sync-pre-pr-lessons.md"
POST_MERGE_SKILL_DRIFT_BEFORE_STATUS_REFERENCE = REFERENCE_DIR / "post-merge-skill-drift-before-status-refresh.md"
PRIVATE_PATH_LEAKS = (
    "/" + "Users/" + "vfrvndtt",
    "/" + "tmp/",
    ".hermes/" + "agent-runs",
)


def test_june_2026_pr_reviewer_evaluation_is_durable_skill_reference():
    assert REFERENCE.exists()
    reference_text = REFERENCE.read_text()
    skill_text = SKILL.read_text()

    assert REFERENCE.name in skill_text
    assert "June 2026 PR Reviewer Quality Evaluation" in reference_text
    assert "live unresolved non-outdated review threads" in reference_text
    assert "CodeRabbit rate-limit" in reference_text


def test_pr49_to_pr52_lessons_are_durable_skill_references():
    skill_text = SKILL.read_text()

    for filename, expected_text in PR49_TO_PR52_REFERENCES.items():
        reference = REFERENCE_DIR / filename
        assert reference.exists()
        assert filename in skill_text
        assert expected_text in reference.read_text()


def test_pr53_to_pr55_skill_sync_lessons_are_durable_skill_reference():
    assert PR53_TO_PR55_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR53_TO_PR55_REFERENCE.read_text()

    assert PR53_TO_PR55_REFERENCE.name in skill_text
    assert "Installed-skill edits must be synced back to the repo source" in reference_text
    assert "Do not let skill-reference sync wording imply new finalization, marker-write, or non-Codex mutating authority" in reference_text


def test_pr56_skill_sync_delivery_lessons_are_durable_skill_reference():
    assert PR56_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR56_REFERENCE.read_text()

    assert PR56_REFERENCE.name in skill_text
    assert "Local git commit signing can break throwaway test repos" in reference_text
    assert "PR-mode backstop verdicts must include the reviewed diff hash" in reference_text
    assert "Manual post-hook cleanup is required when Hermes finalizes outside Claude runtime" in reference_text
    assert "Do not forge Busdriver markers by direct file writes" in reference_text


def test_current_status_readonly_review_lessons_are_durable_skill_reference():
    assert CURRENT_STATUS_READONLY_REVIEW_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = CURRENT_STATUS_READONLY_REVIEW_REFERENCE.read_text()

    assert CURRENT_STATUS_READONLY_REVIEW_REFERENCE.name in skill_text
    assert "Treat the task as review/planning only" in reference_text
    assert "Do not imply a full-suite/smoke result was freshly re-run unless it actually was" in reference_text
    assert "A docs/status refresh must not imply any new authority" in reference_text


def test_continuation_reference_preserves_late_async_follow_up_policy():
    assert CONTINUATION_REFERENCE.exists()
    reference_text = CONTINUATION_REFERENCE.read_text()

    assert "late async reviewer/subagent result arrives after a PR was already merged" in reference_text
    assert "Non-blocking suggestions can become the next tiny follow-up PR" in reference_text
    assert "do not silently ignore them or pretend they were handled in the earlier PR" in reference_text


def test_relay_router_role_policy_references_are_durable_skill_references():
    skill_text = SKILL.read_text()
    references = {
        RELAY_ROUTER_AGENT_ROLE_SPLIT_REFERENCE: [
            "Busdriver + Claude Code = canonical authority",
            "Hard rule: **Only Claude/Busdriver may claim done",
            "future-only design target",
            "non-copyable design-target roles",
            '"avoid_coding_agent_for_review": false',
            '"relay.litmus.reviewer": ["codex"]',
            '"relay.pr.backstop": ["claude-code"]',
            "Authority constraints remain false for all router/status roles",
            "primary-controller agent",
        ],
        RELAY_ROUTER_ROLE_POLICY_REFERENCE: [
            "relay.blueprint.reviewer_2 = claude-code",
            "relay.litmus.reviewer = codex",
            "relay.pr.lead     = fresh-codex",
            "Keep all finalization/commit/push/PR/merge/marker-write flags false",
        ],
    }

    for reference, expected_phrases in references.items():
        assert reference.exists()
        assert f"references/{reference.name}" in skill_text
        reference_text = reference.read_text()
        for phrase in expected_phrases:
            assert phrase in reference_text
        for leaked_path in PRIVATE_PATH_LEAKS:
            assert leaked_path not in reference_text
        if reference == PR78_SKILL_SYNC_PRE_PR_REFERENCE:
            assert "/Volumes/" not in reference_text
            assert "~/.claude/plugins" not in reference_text


def test_skill_sync_pr75_router_role_lessons_are_durable_skill_reference():
    assert SKILL_SYNC_PR75_ROUTER_ROLE_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = SKILL_SYNC_PR75_ROUTER_ROLE_REFERENCE.read_text()

    assert "references/skill-sync-pr75-router-role-lessons.md" in skill_text
    assert "Make copyable config snippets executable against today's helper contracts" in reference_text
    assert "label them as non-copyable/future-only until resolver/status inventory supports them" in reference_text
    assert "avoid_coding_agent_for_review=false" in reference_text
    assert "After every fix push, restart latest-head PR-grind" in reference_text
    assert "docs/status convergence slice" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_relay_completion_sweep_lessons_are_durable_skill_reference():
    assert RELAY_COMPLETION_SWEEP_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = RELAY_COMPLETION_SWEEP_REFERENCE.read_text()

    assert "references/relay-completion-sweep-lessons.md" in skill_text
    assert "Do a final Phase-0 sweep after every merged slice" in reference_text
    assert "PR-grind `BLOCKED` during early CI/reviewer startup is not permission to merge" in reference_text
    assert "Do not keep retrying after a clean PR-grind result" in reference_text


def test_pr60_skill_sync_delivery_lessons_are_durable_skill_reference():
    assert PR60_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR60_REFERENCE.read_text()

    assert "references/pr60-skill-sync-delivery-lessons.md" in skill_text
    assert "Agent-draft invocations need explicit repo/plugin root" in reference_text
    assert "Recover generated ignored-cache postflight blockers surgically" in reference_text
    assert "Durability tests should assert relative reference paths" in reference_text
    assert "After PR creation outside Claude runtime, run post-PR marker cleanup manually" in reference_text
    assert "Release finalization locks with the same branch identity" in reference_text


def test_pr61_to_pr62_continuation_lessons_are_durable_skill_reference():
    assert PR61_TO_PR62_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR61_TO_PR62_REFERENCE.read_text()

    assert "references/pr61-pr62-continuation-lessons.md" in skill_text
    assert "Prefer live observed plugin version over the planned value" in reference_text
    assert "If interrupted after corrected postflight, resume from the dirty docs branch" in reference_text
    assert "finalization_allowed=false" not in reference_text
    assert PRIVATE_PATH_LEAKS[0] not in reference_text
    assert (PRIVATE_PATH_LEAKS[1] + "pr62_current_status_verifier.py") not in reference_text
    assert "<Hermes agent-run baseline.json>" in reference_text


def test_pr63_to_pr64_skill_sync_redaction_lessons_are_durable_skill_reference():
    assert PR63_TO_PR64_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR63_TO_PR64_REFERENCE.read_text()

    assert "references/pr63-pr64-skill-sync-redaction-lessons.md" in skill_text
    assert "Sanitize installed-skill references before repo sync" in reference_text
    assert "Patch installed and repo copies together when redacting synced references" in reference_text
    assert "Durability tests should include negative leakage assertions" in reference_text
    assert "Keep docs/status refreshes evidence-only" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text
    assert "<current-status-verifier>" in reference_text
    assert "<Hermes agent-run baseline.json>" in reference_text


def test_pr66_current_status_refresh_lessons_are_durable_skill_reference():
    assert PR66_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR66_REFERENCE.read_text()

    assert "references/pr66-current-status-refresh-lessons.md" in skill_text
    assert "Keep CURRENT_STATUS refreshes evidence-only" in reference_text
    assert "Do not rely on shell expansion inside `hermes-busdriver-deliver --verifier`" in reference_text
    assert "Do not treat dirty-tree smoke failure as a docs/status regression" in reference_text
    assert "deliver verify on the dirty docs-only draft" in reference_text
    assert "smoke with resolved absolute plugin root on the clean committed branch" in reference_text
    assert "keep the wrapper fail-closed" in reference_text
    assert "Do not convert a nonzero helper return into warning-only success" in reference_text
    assert "6. **Finalization locks are branch-keyed" in reference_text
    assert "7. **End with a final audit after docs/status refresh merges" in reference_text
    assert "saved PR base branch" in reference_text
    assert "main...origin/main" not in reference_text
    assert "switch back to `main`" not in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_pr67_skill_sync_review_fix_lessons_are_durable_skill_reference():
    assert PR67_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR67_REFERENCE.read_text()

    assert "references/pr67-skill-sync-review-fix-lessons.md" in skill_text
    assert "Do not weaken fail-closed helper semantics in lessons" in reference_text
    assert "After PR creation, prefer follow-up commits over amend" in reference_text
    assert "Restart all latest-head evidence after a follow-up push" in reference_text
    assert "Carry the live PR base branch through cleanup lessons" in reference_text
    assert "Do not hard-code `main` or `main...origin/main` in reusable cleanup/final-audit guidance" in reference_text
    assert "switch back to `main`" not in reference_text
    assert "saved base branch against its upstream" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_pr68_late_async_test_followup_lessons_are_durable_skill_reference():
    assert PR68_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR68_REFERENCE.read_text()

    assert "references/pr68-late-async-test-followup-lessons.md" in skill_text
    assert "Classify late async results against current merged state" in reference_text
    assert "Convert cheap test-only non-blocking suggestions into tiny follow-up PRs" in reference_text
    assert "Keep follow-up scope minimal" in reference_text
    assert "Remote branch deletion can already be done by GitHub merge" in reference_text
    assert "remote ref does not exist" in reference_text
    assert "fetch --prune" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_read_only_skill_sync_audit_lessons_are_durable_skill_reference():
    assert READ_ONLY_SKILL_SYNC_AUDIT_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = READ_ONLY_SKILL_SYNC_AUDIT_REFERENCE.read_text()

    assert "references/read-only-skill-sync-audit-lessons.md" in skill_text
    assert "Stay strictly read-only" in reference_text
    assert "Confirm the selected slice from live drift" in reference_text
    assert "Patch installed and repo copies to the same sanitized text" in reference_text
    assert "avoid adding the raw forbidden sentinel strings in new test constants" in reference_text
    assert "include that sanitized reference in the same repo sync" in reference_text
    assert "Validate concurrent skill-sync WIP without taking ownership" in reference_text
    assert "Distinguish pre-WIP failures that prove the drift from post-WIP passes" in reference_text
    assert "run a final whole-skill installed-vs-repo comparison" in reference_text
    assert "classify it as a blocker or explicit scope decision" in reference_text
    assert "Preserve authority boundaries" in reference_text
    assert "CURRENT_STATUS follow-up after merge" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_idle_and_convergence_lessons_are_durable_skill_references():
    skill_text = SKILL.read_text()
    references = {
        IDLE_CLEAN_FINALIZATION_READINESS_REFERENCE: [
            "distinguish **no candidate** from **blocked candidate**",
            "stale-litmus detail in `delivery_status.decision.blockers`",
            "Leave the dirty tree for main Hermes/operator verification/finalization",
        ],
        IDLE_FINALIZATION_READINESS_STATUS_AUDIT_REFERENCE: [
            "distinguish **no finalization candidate exists** from **a candidate exists but is blocked**",
            "Dirty draft changes with stale/blocked litmus evidence must remain `blocked`",
            "PR/merge paths with stale/non-clean evidence must remain blocked",
        ],
        SKILL_SYNC_CURRENT_STATUS_CONVERGENCE_REFERENCE: [
            "Run a whole-skill installed-vs-repo comparison",
            "If final-audit skill maintenance creates a new installed-only class-level reference",
            "sync it to repo with durability assertions, then refresh CURRENT_STATUS against the latest merged head",
            "For a user-explicit safe continuation slice that says to leave the working tree dirty for main Hermes",
            "watch the focused test fail against the stale repo source",
            "Do not commit, push, open a PR, merge, or touch `docs/CURRENT_STATUS.md` unless the user explicitly changes scope",
            "Make `docs/CURRENT_STATUS.md` the last convergence slice whenever possible",
            "Run `git fetch --prune` during merge cleanup before the completion audit",
            "no open PRs, relay topic branches, or stale remote-tracking topic branches remain",
            "CURRENT_STATUS required fresh tokens are present and stale tokens are absent",
            "claude-mem is updated when configured/approved",
        ],
        PR78_SKILL_SYNC_PRE_PR_REFERENCE: [
            "Do a final whole-skill compare after subagents return and after any main-Hermes patch",
            "Use the installed plugin version for smoke/status evidence",
            "Pre-PR dual-voice sequence is still mandatory after commit",
            "After PR reviewer fixes, restart latest-head evidence",
            "Treat reviewer-bot “trivial” comments as blocking when PR-grind classifies them actionable",
            "If skill maintenance during delivery creates a new installed-only reference, sync it in the same PR before status refresh",
        ],
        POST_MERGE_SKILL_DRIFT_BEFORE_STATUS_REFERENCE: [
            "After every skill-sync PR merge, return to the synced base branch and run the whole-skill installed-vs-repo comparison again",
            "Only after installed skill and repo source compare clean should `docs/CURRENT_STATUS.md` become the last evidence-only refresh slice",
            "hermes-busdriver-litmus-status` may report `branch_diff_hash_unavailable: empty diff`",
            "hermes-busdriver-finalization-contract-status` is currently a repo-cwd helper with no `--repo` option",
            "Do not refresh `CURRENT_STATUS` between two skill-sync PRs",
        ],
    }

    for reference, expected_phrases in references.items():
        assert reference.exists()
        assert f"references/{reference.name}" in skill_text
        reference_text = reference.read_text()
        for phrase in expected_phrases:
            assert phrase in reference_text
        for leaked_path in PRIVATE_PATH_LEAKS:
            assert leaked_path not in reference_text
        if reference == PR78_SKILL_SYNC_PRE_PR_REFERENCE:
            assert "/Volumes/" not in reference_text
            assert "~/.claude/plugins" not in reference_text
