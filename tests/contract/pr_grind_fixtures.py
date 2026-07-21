"""Shared PR-grind result fixtures for the delivery-status / readiness / deliver contracts.

A PR-grind result only means something if it is bound to a repo and a PR, so the tests that
feed one through a helper all need the same fully-bound payload. Keeping one builder here stops
the three contract suites from drifting into three different ideas of what "valid" means.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

GITHUB_ORIGIN = "chris-yyau/hermes-busdriver-relay"
PR_GRIND_SCHEMA = "hermes-busdriver-pr-grind-check/v0"
AUTHORITY_FALSE_KEYS = (
    "finalization_allowed",
    "commit_allowed",
    "push_allowed",
    "pr_allowed",
    "merge_allowed",
    "deploy_allowed",
    "release_allowed",
    "publish_allowed",
    "marker_write_allowed",
)


def bind_github_origin(repo: Path, url: str | None = None) -> Path:
    cp = subprocess.run(
        ["git", "remote", "add", "origin", url or f"https://github.com/{GITHUB_ORIGIN}.git"],
        cwd=str(repo), text=True, capture_output=True, check=False,
    )
    assert cp.returncode == 0, cp.stderr
    return repo


def pr_grind_payload(pr: int = 7, status: str = "clean", repository: str = GITHUB_ORIGIN, **overrides: Any) -> dict[str, Any]:
    """A payload shaped exactly like hermes-busdriver-pr-grind-check's live output."""
    payload: dict[str, Any] = {
        "schema": PR_GRIND_SCHEMA,
        "version": 1,
        "ok": True,
        "read_only": True,
        "repository": repository,
        "pr": pr,
        "url": f"https://github.com/{repository}/pull/{pr}",
        "head": "a" * 40,
        "head_repository": repository,
        "head_ref": "feature-branch",
        "base_repository": repository,
        "base": "main",
        "base_sha": "b" * 40,
        "status": status,
        "clean": status == "clean",
        "blockers": [],
        "checks": {"failed": 0, "pending": 0},
        "actionable_comments": [],
        "decision": {
            "status": status,
            "pr_grind_clean": status == "clean",
            **{key: False for key in AUTHORITY_FALSE_KEYS},
            "needs_fix": status == "needs_fix",
            "wait": status == "wait",
            "blocked": status == "blocked",
            "reason": "latest PR HEAD clean" if status == "clean" else status,
        },
    }
    payload.update(overrides)
    return payload
