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


def test_relay_completion_sweep_lessons_are_durable_skill_reference():
    assert RELAY_COMPLETION_SWEEP_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = RELAY_COMPLETION_SWEEP_REFERENCE.read_text()

    assert "references/relay-completion-sweep-lessons.md" in skill_text
    assert "Do a final Phase-0 sweep after every merged slice" in reference_text
    assert "PR-grind `BLOCKED` during early CI/reviewer startup is not permission to merge" in reference_text
    assert "Do not keep retrying after a clean PR-grind result" in reference_text
