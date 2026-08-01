import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
CURRENT_STATUS = ROOT / "docs" / "CURRENT_STATUS.md"
MANIFEST = ROOT / "config" / "trusted-runtime-manifest.json"


def readme_contents_paths() -> set[str]:
    text = README.read_text()
    section = text.split("## Contents", 1)[1].split("## Commands", 1)[0]
    fence = section.split("```text", 1)[1].split("```", 1)[0]
    paths: set[str] = set()
    for line in fence.splitlines():
        token = line.strip().split(maxsplit=1)[0] if line.strip() else ""
        if token and not token.startswith("<"):
            paths.add(token)
    return paths


def test_readme_contents_cover_every_manifested_production_entrypoint():
    manifest = json.loads(MANIFEST.read_text())
    inventory = readme_contents_paths()
    missing = []
    for entrypoint in manifest["production_entrypoints"]:
        covered = entrypoint in inventory or any(
            item.endswith("/") and entrypoint.startswith(item) for item in inventory
        )
        if not covered:
            missing.append(entrypoint)
    assert not missing


def test_current_status_names_security_closure_artifacts_explicitly():
    text = CURRENT_STATUS.read_text()
    assert "PR #168's final exact pre-merge candidate completed `4046 passed, 13 skipped`" in text
    assert "affected focused closure completed `1206 passed`" in text
    required = {
        "config/trusted-runtime-manifest.json",
        "adapters/pi/busdriver-fs-broker.py",
        "adapters/pi/busdriver-tools.ts",
        "scripts/check-required-checks.sh",
        "tests/fixtures/opencode/run-opencode-busdriver-draft",
        "tests/contract/test_required_checks.py",
        "tests/contract/test_trusted_runtime_manifest.py",
        "tests/contract/test_trusted_root_owned_execution.py",
        "tests/contract/test_git_observation_sandbox.py",
        "tests/contract/test_production_dispatch_surface.py",
    }
    named = set(re.findall(r"^- `([^`]+)`", text, flags=re.MULTILINE))
    assert required <= named


def test_current_status_records_merged_authority_chronology():
    text = CURRENT_STATUS.read_text()
    historical_seal = (
        "Historical sealed main immediately before PR #157: commit "
        "`1dc6bbf4eaa91341ecda31d4e8e2a05f80c5de96`, tree "
        "`2b4de738d04283ebf1d945db63bbbf64d2dfdc1f`, with 32-stack "
        "authority result `4090 passed, 14 skipped, 1 deselected`. It is retained "
        "only as provenance and is not current main/top."
    )
    current_main = (
        "The sealed baseline is main commit "
        "`f62cd73fd0ba668372e96f6cc18adb3334010a3a`, tree "
        "`570268a7e16755091627783ecfd33b3d0f3d6515`, after PR #173 added the locked "
        "Cursor candidate lane. The 2026-08-02 promotion attempt for that lane was "
        "adjudicated `PROMOTION_BLOCKED_FAIL_CLOSED`"
    )
    policy_closure = (
        "PR #168 established the current Pi-only executor policy: Pi is the sole "
        "implementation route; Codex remains non-dispatchable fallback-coder/PR-lead metadata"
    )
    live_evidence = (
        "Live post-merge evidence captured before this docs-only refresh branch was opened "
        "reported zero open PRs and issues, a clean `223`-file installed/repository skill comparison"
    )
    section_start = "## Current verification\n\n"
    section_end = "\n## Locations"
    assert section_start in text
    current_section, separator, _ = text.split(section_start, 1)[1].partition(
        section_end
    )
    assert separator

    for required in (historical_seal, current_main, policy_closure, live_evidence):
        assert required in current_section
    assert "UNMERGED / UNSEALED" not in current_section
    assert current_section.index(historical_seal) < current_section.index(
        current_main
    ) < current_section.index(policy_closure) < current_section.index(live_evidence)
    assert "## Historical superseded evidence" in text
