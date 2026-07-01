from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADR_0005 = ROOT / "ADRs" / "0005-finalization-authority-integration-contract.md"
ADR_0006 = ROOT / "ADRs" / "0006-programmatic-dual-review-marker-interop.md"
README = ROOT / "README.md"
SETTLING_V2 = ROOT / "docs" / "settling-checks-v2.md"


def read(path: Path) -> str:
    return path.read_text()


def test_adr_0006_frames_non_mutating_dual_review_marker_interop_contract():
    text = read(ADR_0006)

    for phrase in [
        "non-mutating",
        "does not grant finalization authority",
        "no finalization, dispatch, marker-write, commit, push, PR, merge, deploy, release, or publish authority",
        "Busdriver-native litmus PR mode",
        "Codex lead",
        "read-only backstop",
        "relay.litmus.reviewer",
        "relay.pr.lead",
        "relay.pr.backstop",
        "model/provider/session separation",
        "input digest",
        "reviewed diff hash",
        "reviewer role mapping",
        "reviewer verdicts",
        "confidence/limitations",
        "aggregation decision",
        "timestamps/freshness",
        "data egress/redaction",
        "artifact refs",
        "hermes-busdriver-dual-review-execution/v0",
        "hermes-busdriver-marker-interop/v0",
        "pr-review-passed.local",
        "Hermes must not write",
        "Busdriver trusted writer commands",
        "Busdriver-approved writer identity",
        "atomicity",
        "fsync/rename",
        "path/symlink safety",
        "audit",
        "trust semantics",
        "pass",
        "actionable findings",
        "unavailable",
        "stale",
        "malformed",
        "policy_blocked",
        "all authority false",
        "no raw codex exec",
        "no marker forging",
        "read-only probe",
        "Busdriver-approved invocation seam",
        "marker interop only if Busdriver defines it",
    ]:
        assert phrase in text


def test_adr_0006_is_linked_without_loosening_adr_0005_authority_contract():
    readme = read(README)
    settling_v2 = read(SETTLING_V2)
    adr_0005 = read(ADR_0005)

    assert "ADRs/0006-programmatic-dual-review-marker-interop.md" in readme
    for text in (readme, settling_v2):
        assert "ADR 0006" in text
        assert "design/spike" in text
        assert "ADR 0005" in text
    assert "does **not** grant finalization authority" in adr_0005
    assert '"finalization_allowed": false' in adr_0005
    assert '"marker_write_allowed": false' in adr_0005
