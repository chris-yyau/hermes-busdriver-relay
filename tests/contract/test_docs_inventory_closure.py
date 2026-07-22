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
    required = {
        "config/trusted-runtime-manifest.json",
        "adapters/pi/busdriver-fs-broker.py",
        "adapters/pi/busdriver-tools.ts",
        "scripts/check-required-checks.sh",
        "scripts/opencode/run-opencode-busdriver-draft",
        "tests/contract/test_required_checks.py",
        "tests/contract/test_trusted_runtime_manifest.py",
        "tests/contract/test_trusted_root_owned_execution.py",
        "tests/contract/test_git_observation_sandbox.py",
        "tests/contract/test_production_dispatch_surface.py",
    }
    named = set(re.findall(r"^- `([^`]+)`", text, flags=re.MULTILINE))
    assert required <= named


def test_current_status_records_candidate_authority_chronology():
    text = CURRENT_STATUS.read_text()
    historical_seal = (
        "Historical sealed main immediately before PR #157: commit "
        "`1dc6bbf4eaa91341ecda31d4e8e2a05f80c5de96`, tree "
        "`2b4de738d04283ebf1d945db63bbbf64d2dfdc1f`, with 32-stack "
        "authority result `4090 passed, 14 skipped, 1 deselected`. It is not "
        "current main/top."
    )
    current_base_seal = (
        "Current base main after merged PR #157: commit "
        "`7d7213a6b83f7e68b118c902e0e5381dffbe592c`, tree "
        "`e82d6329651f717443a8b8a9ff0bbe5e80ace133`, separately sealed by "
        "exact-tree full result `4090 passed, 14 skipped, 1 deselected`, "
        "independent security/closure review `PASS`, and postmerge Tests "
        "`29913461631` and Security `29913461640`: `success`. It does not "
        "borrow the 32-stack seal; it has its own runtime reseal authority."
    )
    candidate = (
        "Current candidate status at candidate-verification time: "
        "the policy PR represented by this document is **UNMERGED / UNSEALED** "
        "until its own exact-tree full suite, independent reviews, and delivery "
        "authority pass; it cannot borrow either earlier seal. "
        "External candidate authority binds the exact candidate commit and tree; "
        "the candidate commit SHA is intentionally not embedded because editing "
        "this document changes it."
    )
    assert (
        f"## Current candidate verification\n\n{historical_seal}\n\n"
        f"{current_base_seal}\n\n{candidate}"
    ) in text
    assert "## Historical superseded evidence" in text
    assert text.index(historical_seal) < text.index(current_base_seal) < text.index(
        candidate
    ) < text.index(
        "Latest completed historical exact source validation"
    )
