from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "busdriver-relay" / "SKILL.md"
REFERENCE = ROOT / "skills" / "busdriver-relay" / "references" / "june-2026-pr-reviewer-quality-evaluation.md"


def test_june_2026_pr_reviewer_evaluation_is_durable_skill_reference():
    assert REFERENCE.exists()
    reference_text = REFERENCE.read_text()
    skill_text = SKILL.read_text()

    assert REFERENCE.name in skill_text
    assert "June 2026 PR Reviewer Quality Evaluation" in reference_text
    assert "live unresolved non-outdated review threads" in reference_text
    assert "CodeRabbit rate-limit" in reference_text
