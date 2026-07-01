from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "busdriver-relay" / "SKILL.md"
REFERENCE = ROOT / "skills" / "busdriver-relay" / "references" / "june-2026-pr-reviewer-quality-evaluation.md"
CONTINUATION_REFERENCE = ROOT / "skills" / "busdriver-relay" / "references" / "continuation-subagent-dispatch-lessons.md"


def test_june_2026_pr_reviewer_evaluation_is_durable_skill_reference():
    assert REFERENCE.exists()
    reference_text = REFERENCE.read_text()
    skill_text = SKILL.read_text()

    assert REFERENCE.name in skill_text
    assert "June 2026 PR Reviewer Quality Evaluation" in reference_text
    assert "live unresolved non-outdated review threads" in reference_text
    assert "CodeRabbit rate-limit" in reference_text


def test_continuation_reference_preserves_late_async_follow_up_policy():
    assert CONTINUATION_REFERENCE.exists()
    reference_text = CONTINUATION_REFERENCE.read_text()

    assert "late async reviewer/subagent result arrives after a PR was already merged" in reference_text
    assert "Non-blocking suggestions can become the next tiny follow-up PR" in reference_text
    assert "do not silently ignore them or pretend they were handled in the earlier PR" in reference_text
