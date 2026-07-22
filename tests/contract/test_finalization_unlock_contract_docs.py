from __future__ import annotations

import json
import re
import subprocess
import sys
from html import unescape as html_unescape
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[2]
DOC_POLICY_INVENTORY = ROOT / "config" / "doc-policy-inventory.json"
ADR_0005 = ROOT / "ADRs" / "0005-finalization-authority-integration-contract.md"
ADR_0006 = ROOT / "ADRs" / "0006-programmatic-dual-review-marker-interop.md"
ADR_0008 = ROOT / "ADRs" / "0008-gated-delivery-executor-and-opencode-adapter.md"
README = ROOT / "README.md"
CURRENT_STATUS = ROOT / "docs" / "CURRENT_STATUS.md"
INTEGRATION_CONTRACT = ROOT / "docs" / "hermes-busdriver-integration-contract-v2.md"
SKILL = ROOT / "skills" / "busdriver-relay" / "SKILL.md"
SETTLING_V2 = ROOT / "docs" / "settling-checks-v2.md"
AUTHORITY_MAP = ROOT / "docs" / "coding-workflow-authority-map.md"
SKILL_AUTHORITY_MAP = ROOT / "skills" / "busdriver-relay" / "references" / "coding-workflow-authority-map-v0.1.md"
OPENCODE_README = ROOT / "adapters" / "opencode" / "README.md"
PI_README = ROOT / "adapters" / "pi" / "README.md"
ADR_0003 = ROOT / "ADRs" / "0003-equivalent-gate-runner.md"
ADR_0004 = ROOT / "ADRs" / "0004-draft-agent-launcher.md"
ADR_0007 = ROOT / "ADRs" / "0007-pi-tool-harness-adapter.md"
FULL_ROLE_LESSONS = SKILL.parent / "references" / "full-role-map-dispatchability-lessons.md"
OPENCODE_PROOF_LESSONS = SKILL.parent / "references" / "opencode-fallback-proof-audit-lessons.md"
PI_WORKFLOW = SKILL.parent / "references" / "pi-adapter-candidate-workflow.md"
PI_IMPLEMENTATION_LESSONS = SKILL.parent / "references" / "pi-adapter-implementation-lessons.md"
RELAY_ROLE_SPLIT = SKILL.parent / "references" / "relay-router-agent-role-split.md"

PRODUCTION_AGENT_BLOCKER = "agent_containment_and_credential_broker_unavailable"


def active_agent_policy_docs() -> tuple[Path, ...]:
    inventory = json.loads(DOC_POLICY_INVENTORY.read_text())
    runtime = json.loads((ROOT / "config" / "trusted-runtime-manifest.json").read_text())
    docs = {ROOT / relative for relative in inventory["current_agent_policy"]}
    docs.update(
        ROOT / relative
        for relative in runtime["production_entrypoints"]
        if any(token in relative for token in ("agent-draft", "agent-smoke", "scripts/opencode/", "scripts/pi/"))
    )
    return tuple(sorted(docs))


ACTIVE_AGENT_POLICY_DOCS = active_agent_policy_docs()
SEMANTIC_AGENT_POLICY_DOCS = tuple(sorted({
    *ACTIVE_AGENT_POLICY_DOCS,
    *(ROOT / relative for relative in json.loads(DOC_POLICY_INVENTORY.read_text())["current_reference"]),
}))


def read(path: Path) -> str:
    return path.read_text()


def test_adr_0006_frames_non_mutating_dual_review_marker_interop_contract():
    text = read(ADR_0006)

    for phrase in [
        "non-mutating",
        "does not grant finalization authority",
        "This dual-review/marker-interop surface has no programmatic execution, finalization, marker-write, commit, push, PR, merge, deploy, release, or publish authority",
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


def test_active_docs_mark_push_non_dispatchable_without_atomic_reviewed_base_binding():
    for path in (README, ADR_0005, ADR_0008, CURRENT_STATUS, INTEGRATION_CONTRACT, SETTLING_V2, SKILL):
        text = read(path)
        assert "atomic_push_base_binding_unavailable" in text, path
        assert "policy_blocked" in text, path


def test_active_docs_mark_verifier_and_pr_create_surfaces_policy_blocked():
    for path in (README, ADR_0005, ADR_0008, CURRENT_STATUS, INTEGRATION_CONTRACT, SETTLING_V2, SKILL):
        text = read(path)
        assert "agent_containment_and_credential_broker_unavailable" in text, path
        assert "verifier_containment_unavailable" in text, path
        assert "atomic_pr_create_binding_unavailable" in text, path
        assert "policy_blocked" in text, path


def test_active_docs_mark_pre_pr_review_non_dispatchable_before_lock_and_status():
    paths = (README, ADR_0005, ADR_0006, ADR_0008, CURRENT_STATUS, INTEGRATION_CONTRACT, SETTLING_V2, SKILL)
    forbidden = (
        "`pre-pr-review` invokes",
        "`pre-pr-review` may invoke",
        "`pre-pr-review` and `commit` are gated executor surfaces",
        "`run-review-loop.sh` invoked by `hermes-busdriver-deliver execute --operation pre-pr-review`",
        "except invoking Busdriver-owned trusted writer commands through the gated `pre-pr-review` operation",
    )
    for path in paths:
        text = read(path)
        assert "isolated_review_runtime_unavailable" in text, path
        assert "policy_blocked" in text, path
        for phrase in forbidden:
            assert phrase not in text, (path, phrase)

    readme = read(README)
    assert "execute --operation pre-pr-review|commit` only through its evidence checks and finalization lock" not in readme
    assert "execute --operation commit` only through its evidence checks and finalization lock" in readme
    assert "pre-pr-review` only as a fail-closed policy probe before evidence/status/lock" in readme


def test_active_agent_docs_reject_stale_production_dispatch_claims():
    forbidden = (
        "programmatic dispatch is allowed",
        "programmatic draft dispatch is allowed",
        "dispatchable only through relay preflight/postflight",
        "resolver dispatch is allowed only through the relay adapter",
        "Both production lanes have been verified",
        "real production smoke",
        "launches constrained Pi by default",
        "handles lock, preflight, guarded OpenCode launch",
        "That wrapper handles lock, preflight, Pi launch",
        "then run amend/push/litmus/backstop/PR-grind/merge steps yourself",
        "Agent-draft PATH guards shadow finalization commands",
        "`hermes-busdriver-gate` preflight/postflight around scoped draft-mode agents",
        "Pi-default constrained draft launcher with a verified guarded OpenCode fallback/comparison adapter",
        "verify-only local verifiers",
    )
    for path in ACTIVE_AGENT_POLICY_DOCS:
        text = read(path)
        assert "agent_containment_and_credential_broker_unavailable" in text, path
        for phrase in forbidden:
            assert phrase not in text, (path, phrase)


def test_active_delivery_docs_reject_stale_verifier_and_finalization_claims():
    for path in (README, CURRENT_STATUS, SKILL):
        text = read(path)
        for blocker in (
            "verifier_containment_unavailable",
            "atomic_push_base_binding_unavailable",
            "atomic_pr_create_binding_unavailable",
            "atomic_merge_base_binding_unavailable",
        ):
            assert blocker in text, (path, blocker)
        for phrase in (
            "`execute --operation verify` runs local verifier commands",
            "`execute --operation commit`, `push`, `pr-create`, and `merge` are real side-effect executors",
            "run `hermes-busdriver-deliver execute --operation pre-pr-review|commit|push|pr-create|merge`",
        ):
            assert phrase not in text, (path, phrase)
        assert "no force bypass" in text, path
        assert "non-active tombstone" in text, path
        assert "no recursive pathname deletion" in text, path


_ACTIVATION_VERB_PATTERN = (
    r"(?:launch(?:es|ed|ing)?|start(?:s|ed|ing)?|spawn(?:s|ed|ing)?|"
    r"invoke(?:s|d|ing)?|activate(?:s|d|ing)?|dispatch(?:es|ed|ing|able)|"
    r"run(?:s|ning)?|ran|execute(?:s|d|ing)?|perform(?:s|ed|ing)?|"
    r"boot(?:s|ed|ing)?|fork(?:s|ed|ing)?|initiate(?:s|d|ing)?|"
    r"trigger(?:s|ed|ing)?|schedule(?:s|d|ing)?|call(?:s|ed|ing)?|"
    r"create(?:s|d|ing)?|enable(?:s|d|ing)?|"
    r"kick(?:s|ed|ing)?\s+off|fire(?:s|d|ing)?\s+up|"
    r"bring(?:s|ing)?\s+up|brought\s+up|hand(?:s|ed|ing)?\s+off|"
    r"verified|works?|proves?)"
)
_PRODUCTION_ACTIVATION = re.compile(
    r"\b(?:production|currently?|now)\b"
    r"(?=[^\n]{0,180}\b(?:agents?|drafts?|dispatch|adapters?|workers?|process(?:es)?|smoke)\b)"
    rf"(?=[^\n]{{0,180}}\b{_ACTIVATION_VERB_PATTERN}\b)"
    r"[^\n]{0,180}",
    re.IGNORECASE,
)
_NEGATED_OR_HISTORICAL = re.compile(
    r"(?:agent_containment_and_credential_broker_unavailable|policy[_-]blocked|"
    r"\b(?:block(?:ed|er|ing)?|unavailable|not|no|does\s+not|never|cannot|disabled|false|without|"
    r"non-programmatic|non-dispatchable|non-installed|historical|target-state|superseded|refuses?|"
    r"fail(?:s|ed)?[_ -]?closed|authority-negative)\b)",
    re.IGNORECASE,
)
_STALE_AGENT_CAPABILITY = re.compile(
    r"(?:Hermes may call an implementation agent|first generic executable wrapper|"
    r"opt-in smoke runner for real model-backed adapters|"
    r"Treat Pi as the current constrained default draft lane|"
    r"programmatic_dispatch_allowed\s*=\s*true|dispatch_allowed\s*=\s*true|"
    r"enabled mutating draft lane|preflight/postflight gates around Hermes-launched draft agents)",
    re.IGNORECASE,
)


def assert_no_unqualified_production_agent_capability(text: str) -> None:
    raw_statements = re.split(
        r"(?<=[.!?;])(?:\s+|$)|\n+|\s*(?:—|–|:|/|\(|\))\s*|"
        r"\b(?:but|however|despite|yet|whereas|because|nevertheless|nonetheless|"
        r"although|even\s+though|though|while|since|even\s+as|as|so|when)\b",
        text,
        flags=re.IGNORECASE,
    )
    statements: list[str] = []
    adversative_pattern = r"(?:although|while|even\s+though|though)"
    explicit_activation = re.compile(rf"\b{_ACTIVATION_VERB_PATTERN}\b", re.IGNORECASE)
    contradiction_activation = re.compile(rf"\b{_ACTIVATION_VERB_PATTERN}\b", re.IGNORECASE)
    for statement in raw_statements:
        joined_clauses = re.split(r",|\band\b", statement, flags=re.IGNORECASE)
        activation_clauses = [
            clause for clause in joined_clauses
            if _PRODUCTION_ACTIVATION.search(clause)
            and contradiction_activation.search(clause)
            and not _NEGATED_OR_HISTORICAL.search(clause)
        ]
        if activation_clauses and len(joined_clauses) > 1 and any(
            _NEGATED_OR_HISTORICAL.search(clause) for clause in joined_clauses
        ):
            statements.extend(joined_clauses)
            continue
        leading = re.match(rf"^\s*{adversative_pattern}\b([^,\n]{{0,240}}),\s*(.*)$", statement, flags=re.IGNORECASE)
        if leading:
            statements.extend(leading.groups())
            continue
        suffix = re.split(rf"\b{adversative_pattern}\b", statement, maxsplit=1, flags=re.IGNORECASE)
        if len(suffix) == 2 and explicit_activation.search(suffix[0]):
            statements.extend(suffix)
        else:
            statements.append(statement)
    unqualified = [
        statement.strip()
        for statement in statements
        if _PRODUCTION_ACTIVATION.search(statement)
        and not _NEGATED_OR_HISTORICAL.search(statement)
    ]
    stale = [
        statement.strip()
        for statement in statements
        if _STALE_AGENT_CAPABILITY.search(statement)
        and not _NEGATED_OR_HISTORICAL.search(statement)
    ]
    assert not unqualified, unqualified
    assert not stale, stale


_REFERENCE_MARKDOWN_TARGET = re.compile(
    r"^[ \t]{0,3}\[(?:\\[^\n]|[^\]\\\n]|\n[ \t]*)+\]:[ \t]*(?:\n[ \t]*)?"
    r"(?:<((?:\\[^\n]|[^>\n])+)>|((?:\\[^\n]|[^\s\n])+))"
    r"(?:[ \t]+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^\)\n]*\)))?[ \t]*$",
    re.MULTILINE,
)
_HTML_HREF_TARGET = re.compile(
    r'''<(?:[A-Za-z][A-Za-z0-9:_-]*)\b[^>]*?\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))''',
    re.IGNORECASE,
)
_CODE_SPAN_MARKDOWN_TARGET = re.compile(
    r"(?<!`)`([A-Za-z0-9_./()\-]+\.md(?:#[A-Za-z0-9_./()\-]+)?)`(?!`)"
)
_REPO_LOGICAL_ROOTS = {".claude", "ADRs", "adapters", "docs", "skills", "tests"}


def inline_markdown_targets(text: str) -> set[str]:
    """Extract inline destinations without a regex-shaped CommonMark bypass.

    The scanner starts at every ``](`` token, so nested link labels work, and
    it balances unescaped parentheses in bare destinations. Backslash escapes
    are retained here and normalized by ``repo_markdown_target``.
    """
    targets: set[str] = set()
    cursor = 0
    while (marker := text.find("](", cursor)) >= 0:
        index = marker + 2
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        if text[index] == "<":
            start = index + 1
            index = start
            escaped = False
            while index < len(text):
                char = text[index]
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == ">":
                    targets.add(text[start:index])
                    break
                elif char == "\n":
                    break
                index += 1
        else:
            start = index
            depth = 0
            escaped = False
            while index < len(text):
                char = text[index]
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "(":
                    depth += 1
                elif char == ")":
                    if depth == 0:
                        targets.add(text[start:index])
                        break
                    depth -= 1
                elif char.isspace() and depth == 0:
                    targets.add(text[start:index])
                    break
                index += 1
        cursor = marker + 2
    return targets


def markdown_targets(text: str) -> set[str]:
    targets = inline_markdown_targets(text)
    targets.update(angle or plain for angle, plain in _REFERENCE_MARKDOWN_TARGET.findall(text))
    targets.update(next(value for value in match if value) for match in _HTML_HREF_TARGET.findall(text))
    targets.update(_CODE_SPAN_MARKDOWN_TARGET.findall(text))
    return targets


def repo_markdown_target(source: Path, target: str) -> Path | None:
    normalized = re.sub(r"\\([^\w\s])", r"\1", html_unescape(target.strip()))
    parsed = urlsplit(normalized)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    logical = Path(unquote(parsed.path))
    if logical.suffix.lower() != ".md":
        return None
    if parsed.path.startswith("/"):
        candidate = ROOT / parsed.path.lstrip("/")
    elif parsed.path.startswith(("./", "../")):
        candidate = source.parent / logical
    elif logical.as_posix() == "README.md" or logical.parts[0] in _REPO_LOGICAL_ROOTS:
        candidate = ROOT / logical
    else:
        candidate = source.parent / logical
    resolved = candidate.resolve()
    if not resolved.is_relative_to(ROOT.resolve()):
        return None
    return resolved


def linked_repo_docs(path: Path, text: str) -> set[Path]:
    return {
        resolved
        for target in markdown_targets(text)
        if (resolved := repo_markdown_target(path, target)) is not None
    }


def test_markdown_target_extraction_canonicalizes_inline_relative_fragment_and_reference_links():
    text = """
[settling](./settling-checks-v2.md#current-policy)
[authority](../ADRs/0005-finalization-authority-integration-contract.md)
[angle title](<../ADRs/0006-programmatic-dual-review-marker-interop.md> "current")
[contract][integration]
[integration]: <./hermes-busdriver-integration-contract-v2.md#authority> 'current contract'
[root logical](README.md#overview)
"""

    assert linked_repo_docs(CURRENT_STATUS, text) == {
        SETTLING_V2.resolve(),
        ADR_0005.resolve(),
        ADR_0006.resolve(),
        INTEGRATION_CONTRACT.resolve(),
        README.resolve(),
    }


def test_markdown_target_extraction_handles_nested_labels_balanced_and_escaped_parentheses():
    text = r"""
[nested [label]](./policy(round).md#current)
[escaped](./policy\(round\).md)
"""

    assert linked_repo_docs(CURRENT_STATUS, text) == {
        (CURRENT_STATUS.parent / "policy(round).md").resolve(),
    }


def test_markdown_target_extraction_treats_repo_doc_code_spans_as_policy_edges():
    text = "See `references/git-observation-sandbox-lessons.md#current`; ignore `file.py` and ``literal.md``."
    assert linked_repo_docs(SKILL, text) == {
        (SKILL.parent / "references" / "git-observation-sandbox-lessons.md").resolve(),
    }


@pytest.mark.parametrize(
    "text",
    (
        "[new policy][x\\]]\n\n[x\\]]: references/new-current-policy.md",
        "[new policy][x]\n\n[x]:\nreferences/new-current-policy.md",
        "[new policy][foo bar]\n\n[foo\nbar]: references/new-current-policy.md#current",
    ),
    ids=("escaped-reference-label", "newline-reference-destination", "multiline-reference-label"),
)
def test_commonmark_reference_definitions_cannot_bypass_inventory(text: str):
    expected = (SKILL.parent / "references" / "new-current-policy.md").resolve()
    assert linked_repo_docs(SKILL, text) == {expected}
    with pytest.raises(AssertionError, match="unclassified current doc"):
        authoritative_doc_inventory(text)


def authoritative_doc_inventory(extra_current_text: str = "") -> tuple[dict[Path, str], set[Path]]:
    assert DOC_POLICY_INVENTORY.is_file(), DOC_POLICY_INVENTORY
    raw = json.loads(DOC_POLICY_INVENTORY.read_text())
    assert raw["schema"] == "hermes-busdriver-doc-policy-inventory/v1"
    classifications: dict[Path, str] = {}
    for classification in ("current_agent_policy", "current_reference", "historical"):
        entries = raw[classification]
        assert len(entries) == len(set(entries)), f"duplicate doc classification in {classification}"
        for relative in entries:
            path = (ROOT / relative).resolve()
            assert path not in classifications, f"duplicate doc classification: {relative}"
            assert path.is_file(), f"classified doc missing: {relative}"
            classifications[path] = classification
    skill_text = read(SKILL) + "\n" + extra_current_text
    external_entries = raw["external_or_unavailable_references"]
    assert len(external_entries) == len(set(external_entries)), "duplicate external reference"
    external_or_unavailable: set[Path] = set()
    for relative in external_entries:
        target = repo_markdown_target(SKILL, relative)
        assert target is not None, f"external reference is not a Markdown target: {relative}"
        assert target not in classifications, f"external reference duplicates classified doc: {relative}"
        assert not target.is_file(), f"external reference resolves to existing repo doc: {relative}"
        external_or_unavailable.add(target)
    roots = {
        *(ROOT / relative for relative in raw["roots"]),
        *ROOT.glob("ADRs/*.md"),
    }
    discovered = {path.resolve() for path in roots}
    queue = list(discovered)
    while queue:
        path = queue.pop()
        assert path in classifications, f"unclassified current doc: {path.relative_to(ROOT)}"
        if classifications[path] == "historical":
            continue
        text = read(path)
        if path.resolve() == SKILL.resolve():
            text += "\n" + extra_current_text
        for linked in linked_repo_docs(path, text):
            if linked in external_or_unavailable:
                continue
            if linked not in discovered:
                discovered.add(linked)
                queue.append(linked)
    assert discovered <= set(classifications)
    active = {path for path, classification in classifications.items() if classification != "historical"}
    assert active <= discovered, "unreachable active docs: " + ", ".join(
        str(path.relative_to(ROOT)) for path in sorted(active - discovered)
    )
    return classifications, discovered


def test_agent_capability_semantic_guard_rejects_reviewer_mutants():
    for mutant in (
        "Production launches agents for scoped drafts.",
        "Production performs real-agent verification with local verifiers.",
        "The current production route is verified and enabled for draft dispatch.",
    ):
        with pytest.raises(AssertionError):
            assert_no_unqualified_production_agent_capability(mutant)


@pytest.mark.parametrize(
    "mutant",
    (
        "Production dispatch is blocked, but production launches agents for scoped drafts.",
        "Current real-agent smoke proves production dispatch works.",
        "Although production dispatch is blocked, production launches agents for scoped drafts.",
        "While production dispatch is blocked, production launches agents for scoped drafts.",
        "Production launches agents for scoped drafts despite being policy_blocked.",
        "Production launches agents for scoped drafts although production dispatch is blocked.",
        "Production launches agents for scoped drafts while production dispatch is blocked.",
        "Even though production dispatch is blocked, production launches agents for scoped drafts.",
    ),
    ids=("contradiction", "current-smoke-as-proof", "although-prefix", "while-prefix", "despite", "although-suffix", "while-suffix", "even-though-prefix"),
)
def test_agent_capability_semantic_guard_rejects_trust_boundary_mutants(mutant: str):
    with pytest.raises(AssertionError):
        assert_no_unqualified_production_agent_capability(mutant)


def test_authoritative_doc_inventory_covers_project_guide_and_linked_current_references():
    classifications, discovered = authoritative_doc_inventory()
    assert (ROOT / ".claude" / "CLAUDE.md").resolve() in discovered
    assert classifications[(SKILL.parent / "references" / "relay-v1-session-lessons.md").resolve()] == "historical"
    assert classifications[PI_IMPLEMENTATION_LESSONS.resolve()] == "historical"
    assert classifications[RELAY_ROLE_SPLIT.resolve()] == "historical"
    assert classifications[SKILL_AUTHORITY_MAP.resolve()] == "current_agent_policy"
    assert classifications[FULL_ROLE_LESSONS.resolve()] == "current_agent_policy"
    assert all(classifications[path] != "historical" for path in map(Path.resolve, ROOT.glob("ADRs/*.md")))


def test_authoritative_doc_inventory_rejects_newly_linked_current_reference_omission():
    with pytest.raises(AssertionError, match="unclassified current doc"):
        authoritative_doc_inventory("See [new policy](references/new-current-policy.md).")


def test_authoritative_doc_inventory_scans_every_classified_active_doc(monkeypatch):
    real_read = read

    def mutated_read(path: Path) -> str:
        text = real_read(path)
        if path.resolve() == CURRENT_STATUS.resolve():
            text += "\nSee [new current policy](new-current-policy.md#authority).\n"
        return text

    monkeypatch.setitem(authoritative_doc_inventory.__globals__, "read", mutated_read)
    with pytest.raises(AssertionError, match="unclassified current doc"):
        authoritative_doc_inventory()


@pytest.mark.parametrize(
    "html",
    (
        '<a href="references/new-current-policy.md#current">policy</a>',
        '<map name="policy"><area href="references/new-current-policy.md#current" alt="policy"></map>',
        '<link rel="help" href="references/new-current-policy.md#current">',
    ),
    ids=("a", "area", "link"),
)
def test_authoritative_doc_inventory_rejects_html_local_doc_link(html: str):
    with pytest.raises(AssertionError, match="unclassified current doc"):
        authoritative_doc_inventory(html)


@pytest.mark.parametrize(
    "relative",
    (
        "scripts/hermes-busdriver-agent-draft",
        "scripts/pi/run-pi-busdriver-draft",
        "scripts/opencode/run-opencode-busdriver-draft",
    ),
)
def test_production_agent_help_renders_exact_fixed_blocker(relative: str):
    cp = subprocess.run([sys.executable, str(ROOT / relative), "--help"], text=True, capture_output=True, check=False)
    assert cp.returncode == 0
    assert PRODUCTION_AGENT_BLOCKER in cp.stdout
    assert "exits nonzero before dispatch" in cp.stdout


@pytest.mark.parametrize("cross_class", (False, True), ids=("same-list", "cross-class"))
def test_authoritative_doc_inventory_rejects_duplicate_classifications(
    monkeypatch, tmp_path: Path, cross_class: bool
):
    raw = json.loads(DOC_POLICY_INVENTORY.read_text())
    duplicate = raw["current_agent_policy"][0]
    raw["current_reference" if cross_class else "current_agent_policy"].append(duplicate)
    mutant = tmp_path / "duplicate-doc-policy-inventory.json"
    mutant.write_text(json.dumps(raw))
    monkeypatch.setitem(authoritative_doc_inventory.__globals__, "DOC_POLICY_INVENTORY", mutant)

    with pytest.raises(AssertionError, match="duplicate doc classification"):
        authoritative_doc_inventory()


def test_authoritative_doc_inventory_rejects_existing_repo_doc_moved_to_external(
    monkeypatch, tmp_path: Path
):
    raw = json.loads(DOC_POLICY_INVENTORY.read_text())
    relative = "docs/settling-checks-v2.md"
    raw["current_reference"].remove(relative)
    raw["external_or_unavailable_references"].append(relative)
    mutant = tmp_path / "externalized-doc-policy-inventory.json"
    mutant.write_text(json.dumps(raw))
    monkeypatch.setitem(authoritative_doc_inventory.__globals__, "DOC_POLICY_INVENTORY", mutant)

    with pytest.raises(AssertionError, match="external reference resolves to existing repo doc"):
        authoritative_doc_inventory()


def test_authoritative_doc_inventory_rejects_unclassified_relative_markdown_target():
    with pytest.raises(AssertionError, match="unclassified current doc.*SECURITY.md"):
        authoritative_doc_inventory("See [security policy](../../SECURITY.md#reporting).")


def test_current_reference_semantic_activation_mutant_is_in_all_doc_sweep():
    raw = json.loads(DOC_POLICY_INVENTORY.read_text())
    current_references = {(ROOT / relative).resolve() for relative in raw["current_reference"]}
    assert current_references <= set(SEMANTIC_AGENT_POLICY_DOCS)
    with pytest.raises(AssertionError):
        assert_no_unqualified_production_agent_capability(
            read(next(iter(current_references))) + "\nProduction launches agents for scoped drafts."
        )


def test_every_historical_doc_has_conspicuous_non_production_banner_and_current_authority_pointer():
    raw = json.loads(DOC_POLICY_INVENTORY.read_text())
    for relative in raw["historical"]:
        banner = "\n".join(read(ROOT / relative).splitlines()[:5])
        assert "HISTORICAL / SUPERSEDED" in banner, relative
        assert "NON-PRODUCTION" in banner, relative
        assert "docs/coding-workflow-authority-map.md" in banner, relative


@pytest.mark.parametrize(
    "clean",
    (
        "Production never starts agent processes.",
        "Production does not spawn agent processes.",
        "Production invokes no agent processes.",
        "Production cannot activate agent adapters.",
        "Production starts no agent processes while dispatch is blocked.",
        "Production dispatch remains blocked while agent_containment_and_credential_broker_unavailable is active.",
        "Current tests launch agent fixtures without production dispatch.",
        "Historical production launched agents before this policy was superseded.",
        "The current production adapter is non-dispatchable and never runs agents.",
        "Target-state production launches agents only after a future broker exists.",
    ),
)
def test_semantic_activation_guard_accepts_explicitly_noncapable_controls(clean: str):
    assert_no_unqualified_production_agent_capability(clean)


@pytest.mark.parametrize("path", SEMANTIC_AGENT_POLICY_DOCS, ids=lambda path: str(path.relative_to(ROOT)))
@pytest.mark.parametrize(
    "mutant",
    (
        "Production launches agents for scoped drafts.",
        "Production performs real-agent verification with local verifiers.",
        "The current production route is verified and enabled for draft dispatch.",
        "Production dispatch is blocked, but production launches agents for scoped drafts.",
        "Production launches agents for scoped drafts, production dispatch is blocked.",
        "Production launches agents for scoped drafts and production dispatch is blocked.",
        "Production dispatch is blocked, yet production launches agents for scoped drafts.",
        "Production dispatch is blocked whereas production launches agents for scoped drafts.",
        "Production dispatch is blocked — production launches agents for scoped drafts.",
        "Production dispatch is blocked: production launches agents for scoped drafts.",
        "Production dispatch is blocked because production launches agents for scoped drafts.",
        "Production starts the configured agent process.",
        "Production spawns the configured agent process.",
        "Production invokes the configured agent process.",
        "Production activates the configured agent process.",
        "Current real-agent smoke proves production dispatch works.",
        "Production dispatch is blocked as production starts agents.",
        "Production dispatch is blocked even as production invokes agents.",
        "Production dispatch is blocked although production launches agents.",
        "Production dispatch is blocked even though production invokes agents.",
        "Production dispatch is blocked though production spawns agents.",
        "Production dispatch is blocked while production starts agents.",
        "Production dispatch is blocked since production launches agents.",
        "Production dispatch is blocked so production spawns agents.",
        "Production dispatch is blocked when production activates agents.",
        "Production dispatch is blocked / production launches agents.",
        "Production dispatch is blocked (production starts agents).",
        "Production boots the configured agent process.",
        "Production forks the configured agent process.",
        "Production initiates the configured agent process.",
        "Production triggers the configured agent process.",
        "Production schedules the configured agent process.",
        "Production calls the configured agent process.",
        "Production creates the configured agent process.",
        "Production enables the configured agent adapter.",
        "Production kicks off the configured agent process.",
        "Production fires up the configured agent process.",
        "Production brings up the configured agent process.",
        "Production hands off to the configured agent process.",
    ),
    ids=(
        "launches", "real-verification", "verified-enabled", "contradiction",
        "comma-contradiction", "and-contradiction", "yet-contradiction",
        "whereas-contradiction", "em-dash-contradiction", "colon-contradiction",
        "because-contradiction", "starts", "spawns", "invokes", "activates",
        "current-smoke-as-proof", "as-boundary", "even-as-boundary",
        "although-reverse", "even-though-reverse", "though-reverse", "while-reverse",
        "since-boundary", "so-boundary", "when-boundary", "slash-boundary",
        "parenthetical-boundary", "boots", "forks", "initiates", "triggers",
        "schedules", "calls", "creates", "enables", "kicks-off", "fires-up",
        "brings-up", "hands-off",
    ),
)
def test_each_active_agent_policy_doc_rejects_semantic_activation_mutants(path: Path, mutant: str):
    clean = read(path)
    assert_no_unqualified_production_agent_capability(clean)
    with pytest.raises(AssertionError):
        assert_no_unqualified_production_agent_capability(clean + "\n\n" + mutant)


def test_all_active_agent_policy_docs_are_blocked_and_semantically_consistent():
    for path in ACTIVE_AGENT_POLICY_DOCS:
        text = read(path)
        assert PRODUCTION_AGENT_BLOCKER in text, path
        assert_no_unqualified_production_agent_capability(text)


# --- v16-r21: observed installed plugin version vs pinned trust-manifest version ---

def test_docs_distinguish_observed_plugin_version_from_trust_manifest_version():
    manifest = json.loads((ROOT / "config" / "trusted-runtime-manifest.json").read_text())
    pinned = manifest["busdriver"]["version"]
    status_text = CURRENT_STATUS.read_text()
    readme_text = README.read_text()

    # The smoke observation and the reviewed trust pin are different facts; a doc that names
    # only one of them reads as if the manifest tracked the installed plugin.
    assert "1.91.2" in status_text
    assert pinned in status_text
    assert "trust-manifest" in status_text or "trusted-runtime-manifest" in status_text
    assert pinned in readme_text
