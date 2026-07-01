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


def test_continuation_reference_preserves_late_async_follow_up_policy():
    assert CONTINUATION_REFERENCE.exists()
    reference_text = CONTINUATION_REFERENCE.read_text()

    assert "late async reviewer/subagent result arrives after a PR was already merged" in reference_text
    assert "Non-blocking suggestions can become the next tiny follow-up PR" in reference_text
    assert "do not silently ignore them or pretend they were handled in the earlier PR" in reference_text
