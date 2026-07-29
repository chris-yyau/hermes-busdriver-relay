import json
import re
import subprocess
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
    section_start = "## Current verification\n\n"
    section_end = "\n## Locations"
    assert section_start in text
    current_section, separator, _ = text.split(section_start, 1)[1].partition(
        section_end
    )
    assert separator

    base = re.search(
        r"Verified repository base immediately preceding this docs/contract refresh "
        r"is .+ at commit `([0-9a-f]{40})`, tree `([0-9a-f]{40})`\.",
        current_section,
    )
    live = re.search(
        r"Live post-merge evidence captured before this docs-only refresh "
        r"branch was opened reported zero open PRs and issues, a clean `\d+`-file "
        r"installed/repository skill comparison",
        current_section,
    )
    assert base
    base_commit, documented_tree = base.groups()
    base_tree = subprocess.run(
        ["git", "rev-parse", f"{base_commit}^{{tree}}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if base_tree.returncode == 0:
        assert base_tree.stdout.strip() == documented_tree
    else:
        # Depth-1 clones and source archives legitimately lack the documented
        # historical commit object; a full non-shallow Git checkout must still
        # fail here so a typo in the documented commit cannot false-green.
        shallow = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert shallow.stdout.strip() == "true" or not (ROOT / ".git").exists(), (
            base_tree.stderr.strip()
        )
    assert live
    assert historical_seal in current_section
    assert "Current main after" not in current_section
    assert "UNMERGED / UNSEALED" not in current_section
    assert current_section.index(historical_seal) < base.start() < live.start()
    assert "## Historical superseded evidence" in text
