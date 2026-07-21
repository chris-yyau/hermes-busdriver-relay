> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Litmus Status Pathspec-Environment PR-Grind Lessons

Context: while delivering the read-only `scripts/hermes-busdriver-litmus-status` helper, PR reviewer bots found a real blocker after commit/PR creation: `sanitized_git_env()` stripped repository-identity variables but did not strip Git pathspec-mode variables. This let inherited caller state change the `.gitattributes` probe semantics.

## Durable lesson

When a relay helper uses Git pathspecs for safety probes — especially magic pathspecs such as `:(glob)**/.gitattributes` — sanitize Git pathspec environment variables in addition to repository identity variables.

Strip at least:

- `GIT_LITERAL_PATHSPECS`
- `GIT_GLOB_PATHSPECS`
- `GIT_NOGLOB_PATHSPECS`
- `GIT_ICASE_PATHSPECS`

Why: with `GIT_LITERAL_PATHSPECS=1`, Git treats `:(glob)**/.gitattributes` as a literal path instead of a glob. A nested `.gitattributes` can then be missed, and the helper may compute a branch diff hash under unsafe diff-attribute conditions instead of failing closed.

## Regression test shape

Add a focused test before fixing:

```python
def test_branch_diff_hash_blocks_nested_gitattributes_when_pathspec_env_is_set(tmp_path: Path):
    repo = init_repo(tmp_path / "repo", branch=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "pr-review-passed.local").write_text("stale\n")
    nested = repo / "nested"
    nested.mkdir()
    (nested / ".gitattributes").write_text("*.txt diff=word\n")
    env = {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}

    data = invoke(repo, env=env)

    assert data["ok"] is False
    assert data["repo"]["branch_diff_hash"] is None
    assert any("diff attributes configured" in blocker for blocker in data["decision"]["blockers"])
    assert data["decision"]["status"] == "blocked"
    assert_no_authority(data["decision"])
```

Then extend the sanitizer and rerun the focused test plus the full contract suite and relay smoke.

## Delivery-mode consequence

Any amend/fix after PR review changes the branch diff hash. Treat all previous PR-mode artifacts as stale:

1. rerun PR-mode Codex lead;
2. rerun/read-only backstop on the new `base...HEAD` diff;
3. persist fresh backstop verdict through the trusted writer;
4. write a fresh PR marker;
5. force-with-lease push;
6. restart latest-head PR grind.

Do not merge on stale pre-fix PR marker evidence, even if all CI checks are green.
