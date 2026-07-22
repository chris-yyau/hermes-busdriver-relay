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
PR53_TO_PR55_REFERENCE = REFERENCE_DIR / "pr53-pr55-skill-sync-lessons.md"
PR56_REFERENCE = REFERENCE_DIR / "pr56-skill-sync-delivery-lessons.md"
CURRENT_STATUS_READONLY_REVIEW_REFERENCE = REFERENCE_DIR / "current-status-readonly-review-lessons.md"
RELAY_COMPLETION_SWEEP_REFERENCE = REFERENCE_DIR / "relay-completion-sweep-lessons.md"
PR60_REFERENCE = REFERENCE_DIR / "pr60-skill-sync-delivery-lessons.md"
PR61_TO_PR62_REFERENCE = REFERENCE_DIR / "pr61-pr62-continuation-lessons.md"
PR63_TO_PR64_REFERENCE = REFERENCE_DIR / "pr63-pr64-skill-sync-redaction-lessons.md"
PR66_REFERENCE = REFERENCE_DIR / "pr66-current-status-refresh-lessons.md"
PR67_REFERENCE = REFERENCE_DIR / "pr67-skill-sync-review-fix-lessons.md"
PR68_REFERENCE = REFERENCE_DIR / "pr68-late-async-test-followup-lessons.md"
READ_ONLY_SKILL_SYNC_AUDIT_REFERENCE = REFERENCE_DIR / "read-only-skill-sync-audit-lessons.md"
ROADMAP_READONLY_AUDIT_REFERENCE = REFERENCE_DIR / "roadmap-readonly-audit-lessons.md"
PERIODIC_DISK_CLEANUP_CRON_REFERENCE = REFERENCE_DIR / "periodic-disk-cleanup-cron-lessons.md"
PR98_ROADMAP_BRIEF_CLEANUP_REFERENCE = REFERENCE_DIR / "pr98-roadmap-brief-cleanup-lessons.md"
IDLE_CLEAN_FINALIZATION_READINESS_REFERENCE = REFERENCE_DIR / "idle-clean-finalization-readiness-lessons.md"
IDLE_FINALIZATION_READINESS_STATUS_AUDIT_REFERENCE = REFERENCE_DIR / "idle-finalization-readiness-status-audit-lessons.md"
SKILL_SYNC_CURRENT_STATUS_CONVERGENCE_REFERENCE = REFERENCE_DIR / "skill-sync-current-status-convergence-lessons.md"
RELAY_ROUTER_AGENT_ROLE_SPLIT_REFERENCE = REFERENCE_DIR / "relay-router-agent-role-split.md"
RELAY_ROUTER_ROLE_POLICY_REFERENCE = REFERENCE_DIR / "relay-router-role-policy-2026-07.md"
SKILL_SYNC_PR75_ROUTER_ROLE_REFERENCE = REFERENCE_DIR / "skill-sync-pr75-router-role-lessons.md"
PR78_SKILL_SYNC_PRE_PR_REFERENCE = REFERENCE_DIR / "pr78-skill-sync-pre-pr-lessons.md"
POST_MERGE_SKILL_DRIFT_BEFORE_STATUS_REFERENCE = REFERENCE_DIR / "post-merge-skill-drift-before-status-refresh.md"
FINAL_AUDIT_SKILL_MAINTENANCE_RECURSION_REFERENCE = REFERENCE_DIR / "final-audit-skill-maintenance-recursion.md"
PI_ADAPTER_CANDIDATE_WORKFLOW_REFERENCE = REFERENCE_DIR / "pi-adapter-candidate-workflow.md"
PI_ADAPTER_IMPLEMENTATION_LESSONS_REFERENCE = REFERENCE_DIR / "pi-adapter-implementation-lessons.md"
CODING_WORKFLOW_AUTHORITY_MAP_REFERENCE = REFERENCE_DIR / "coding-workflow-authority-map-v0.1.md"
PR106_EXPANDED_SKILL_SYNC_PR_GRIND_REFERENCE = (
    REFERENCE_DIR / "pr106-expanded-skill-sync-pr-grind-lessons.md"
)
PI_ADAPTER_ASYNC_REVIEW_FIX_REFERENCE = (
    REFERENCE_DIR / "pi-adapter-async-review-fix-lessons.md"
)
PR108_PI_AUTHORITY_SYNC_REFERENCE = (
    REFERENCE_DIR / "pr108-pi-authority-sync-delivery-lessons.md"
)
PR109_PI_ADAPTER_FINAL_PR_GRIND_REFERENCE = (
    REFERENCE_DIR / "pr109-pi-adapter-final-pr-grind-lessons.md"
)
PR109_PI_ADAPTER_REVIEW_REBASE_REFERENCE = (
    REFERENCE_DIR / "pr109-pi-adapter-review-rebase-lessons.md"
)
FULL_ROLE_MAP_DISPATCHABILITY_REFERENCE = (
    REFERENCE_DIR / "full-role-map-dispatchability-lessons.md"
)
FULL_ROLE_MAP_RESOLVER_SLICE_REFERENCE = (
    REFERENCE_DIR / "full-role-map-resolver-slice-lessons.md"
)
PR112_PI_DEFAULT_DOGFOOD_REFERENCE = (
    REFERENCE_DIR / "pr112-pi-default-dogfood-lessons.md"
)
RELAY_LIVE_CONFIG_RESTORATION_REFERENCE = (
    REFERENCE_DIR / "relay-live-config-restoration-lessons.md"
)
ADR0005_AUTHORITY_SOURCE_STATUS_REFERENCE = (
    REFERENCE_DIR / "adr0005-authority-source-status-lessons.md"
)
PR118_SKILL_SYNC_DELIVERY_REFERENCE = (
    REFERENCE_DIR / "pr118-skill-sync-delivery-lessons.md"
)
LOCK_CLI_USAGE_PITFALLS_REFERENCE = REFERENCE_DIR / "lock-cli-usage-pitfalls.md"
OPENCODE_FALLBACK_PROOF_AUDIT_REFERENCE = REFERENCE_DIR / "opencode-fallback-proof-audit-lessons.md"
GATED_FINALIZATION_EXECUTOR_OPENCODE_REFERENCE = REFERENCE_DIR / "gated-finalization-executor-opencode-lessons.md"
PRIVATE_PATH_LEAKS = (
    "/" + "Users/" + "vfrvndtt",
    "/" + "tmp/",
    ".hermes/" + "agent-runs",
)


def test_all_skill_references_end_with_terminal_newline():
    missing_terminal_newline = [
        reference.relative_to(REFERENCE_DIR).as_posix()
        for reference in sorted(REFERENCE_DIR.rglob("*.md"))
        if not reference.read_bytes().endswith(b"\n")
    ]

    assert missing_terminal_newline == []


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


def test_pr53_to_pr55_skill_sync_lessons_are_durable_skill_reference():
    assert PR53_TO_PR55_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR53_TO_PR55_REFERENCE.read_text()

    assert PR53_TO_PR55_REFERENCE.name in skill_text
    assert "Installed-skill edits must be synced back to the repo source" in reference_text
    assert "Do not let skill-reference sync wording imply new finalization, marker-write, or non-Codex mutating authority" in reference_text


def test_pr56_skill_sync_delivery_lessons_are_durable_skill_reference():
    assert PR56_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR56_REFERENCE.read_text()

    assert PR56_REFERENCE.name in skill_text
    assert "Local git commit signing can break throwaway test repos" in reference_text
    assert "PR-mode backstop verdicts must include the reviewed diff hash" in reference_text
    assert "Manual post-hook cleanup is required when Hermes finalizes outside Claude runtime" in reference_text
    assert "Do not forge Busdriver markers by direct file writes" in reference_text


def test_current_status_readonly_review_lessons_are_durable_skill_reference():
    assert CURRENT_STATUS_READONLY_REVIEW_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = CURRENT_STATUS_READONLY_REVIEW_REFERENCE.read_text()

    assert CURRENT_STATUS_READONLY_REVIEW_REFERENCE.name in skill_text
    assert "Treat the task as review/planning only" in reference_text
    assert "Do not imply a full-suite/smoke result was freshly re-run unless it actually was" in reference_text
    assert "A docs/status refresh must not imply any new authority" in reference_text


def test_continuation_reference_preserves_late_async_follow_up_policy():
    assert CONTINUATION_REFERENCE.exists()
    reference_text = CONTINUATION_REFERENCE.read_text()

    assert "late async reviewer/subagent result arrives after a PR was already merged" in reference_text
    assert "Non-blocking suggestions can become the next tiny follow-up PR" in reference_text
    assert "do not silently ignore them or pretend they were handled in the earlier PR" in reference_text


def test_relay_router_role_policy_references_are_durable_skill_references():
    skill_text = SKILL.read_text()
    references = {
        RELAY_ROUTER_AGENT_ROLE_SPLIT_REFERENCE: [
            "Busdriver + Claude Code = canonical authority",
            "Hard rule: **Only Claude/Busdriver may claim done",
            "Resolver-ready role inventory",
            "Copyable config example",
            '"avoid_coding_agent_for_review": true',
            '"relay.litmus.reviewer": ["codex"]',
            '"relay.pr.backstop": ["claude-code"]',
            "Authority constraints remain false for all router/status roles",
            "Codex is implementation-primary metadata and PR lead by user policy",
            "agent_containment_and_credential_broker_unavailable",
            "primary-controller agent",
        ],
        RELAY_ROUTER_ROLE_POLICY_REFERENCE: [
            "relay.blueprint.reviewer_2 = claude-code",
            "relay.litmus.reviewer = codex",
            "relay.pr.lead     = codex",
            "relay.impl.primary   = pi",
            "**OpenCode** is the intended Pi fallback / China-model comparison candidate",
            "Keep all finalization/commit/push/PR/merge/marker-write flags false",
        ],
    }

    for reference, expected_phrases in references.items():
        assert reference.exists()
        assert f"references/{reference.name}" in skill_text
        reference_text = reference.read_text()
        for phrase in expected_phrases:
            assert phrase in reference_text
        for leaked_path in PRIVATE_PATH_LEAKS:
            assert leaked_path not in reference_text
        if reference == PR78_SKILL_SYNC_PRE_PR_REFERENCE:
            assert "/Volumes/" not in reference_text
            assert "~/.claude/plugins" not in reference_text


def test_skill_sync_pr75_router_role_lessons_are_durable_skill_reference():
    assert SKILL_SYNC_PR75_ROUTER_ROLE_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = SKILL_SYNC_PR75_ROUTER_ROLE_REFERENCE.read_text()

    assert "references/skill-sync-pr75-router-role-lessons.md" in skill_text
    assert "Make copyable config snippets executable against today's helper contracts" in reference_text
    assert "current first-class role inventory" in reference_text
    assert "avoid_coding_agent_for_review=true" in reference_text
    assert "After every fix push, restart latest-head PR-grind" in reference_text
    assert "docs/status convergence slice" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_relay_completion_sweep_lessons_are_durable_skill_reference():
    assert RELAY_COMPLETION_SWEEP_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = RELAY_COMPLETION_SWEEP_REFERENCE.read_text()

    assert "references/relay-completion-sweep-lessons.md" in skill_text
    assert "Do a final Phase-0 sweep after every merged slice" in reference_text
    assert "PR-grind `BLOCKED` during early CI/reviewer startup is not permission to merge" in reference_text
    assert "Do not keep retrying after a clean PR-grind result" in reference_text


def test_pr60_skill_sync_delivery_lessons_are_durable_skill_reference():
    assert PR60_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR60_REFERENCE.read_text()

    assert "references/pr60-skill-sync-delivery-lessons.md" in skill_text
    assert "Agent-draft invocations need explicit repo/plugin root" in reference_text
    assert "Recover generated ignored-cache postflight blockers surgically" in reference_text
    assert "Durability tests should assert relative reference paths" in reference_text
    assert "After PR creation outside Claude runtime, run post-PR marker cleanup manually" in reference_text
    assert "Release finalization locks with the same branch identity" in reference_text


def test_pr61_to_pr62_continuation_lessons_are_durable_skill_reference():
    assert PR61_TO_PR62_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR61_TO_PR62_REFERENCE.read_text()

    assert "references/pr61-pr62-continuation-lessons.md" in skill_text
    assert "Prefer live observed plugin version over the planned value" in reference_text
    assert "If interrupted after corrected postflight, resume from the dirty docs branch" in reference_text
    assert "finalization_allowed=false" not in reference_text
    assert PRIVATE_PATH_LEAKS[0] not in reference_text
    assert (PRIVATE_PATH_LEAKS[1] + "pr62_current_status_verifier.py") not in reference_text
    assert "<Hermes agent-run baseline.json>" in reference_text


def test_pr63_to_pr64_skill_sync_redaction_lessons_are_durable_skill_reference():
    assert PR63_TO_PR64_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR63_TO_PR64_REFERENCE.read_text()

    assert "references/pr63-pr64-skill-sync-redaction-lessons.md" in skill_text
    assert "Sanitize installed-skill references before repo sync" in reference_text
    assert "Patch installed and repo copies together when redacting synced references" in reference_text
    assert "Durability tests should include negative leakage assertions" in reference_text
    assert "Keep docs/status refreshes evidence-only" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text
    assert "<current-status-verifier>" in reference_text
    assert "<Hermes agent-run baseline.json>" in reference_text


def test_pr66_current_status_refresh_lessons_are_durable_skill_reference():
    assert PR66_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR66_REFERENCE.read_text()

    assert "references/pr66-current-status-refresh-lessons.md" in skill_text
    assert "Keep CURRENT_STATUS refreshes evidence-only" in reference_text
    assert "Do not rely on shell expansion inside `hermes-busdriver-deliver --verifier`" in reference_text
    assert "Do not treat dirty-tree smoke failure as a docs/status regression" in reference_text
    assert "deliver verify on the dirty docs-only draft" in reference_text
    assert "smoke with resolved absolute plugin root on the clean committed branch" in reference_text
    assert "keep the wrapper fail-closed" in reference_text
    assert "Do not convert a nonzero helper return into warning-only success" in reference_text
    assert "6. **Finalization locks are branch-keyed" in reference_text
    assert "7. **End with a final audit after docs/status refresh merges" in reference_text
    assert "saved PR base branch" in reference_text
    assert "Distinguish installed-plugin smoke evidence from source-checkout version evidence" in reference_text
    assert "Treat clean-main litmus empty-diff output as marker-sanity evidence" in reference_text
    assert "Run `finalization-contract-status` from the target repo cwd" in reference_text
    assert "Use a doc freshness validator before committing" in reference_text
    assert "If the final completion audit finds skill drift created by the status refresh itself" in reference_text
    assert "restart the final audit from the saved PR base branch" in reference_text
    assert "Do not mark the relay complete while installed skill and repo skill source differ" in reference_text
    assert "Move temp/cache roots off the system volume when long verification loops hit ENOSPC" in reference_text
    assert "$SPACIOUS_RUNTIME_VOLUME/.hermes-runtime" in reference_text
    assert "export `TMPDIR`, `UV_CACHE_DIR`, `PIP_CACHE_DIR`, and `XDG_CACHE_HOME`" in reference_text
    assert "This is a durable workaround for macOS APFS system-volume pressure" in reference_text
    assert "/Volumes/" not in reference_text
    assert "main...origin/main" not in reference_text
    assert "switch back to `main`" not in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_final_audit_skill_maintenance_recursion_lessons_are_durable_skill_reference():
    assert FINAL_AUDIT_SKILL_MAINTENANCE_RECURSION_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = FINAL_AUDIT_SKILL_MAINTENANCE_RECURSION_REFERENCE.read_text()

    assert "references/final-audit-skill-maintenance-recursion.md" in skill_text
    assert "avoid infinite skill-sync recursion" in reference_text
    assert "Batch skill-maintenance lessons before the final status refresh" in reference_text
    assert "do not add more skill lessons unless safety/correctness requires it" in reference_text
    assert "Handle explicit skill-library review requests as a single consolidated maintenance step" in reference_text
    assert "Do not create a new one-session skill" in reference_text
    assert "Treat meta skill-review prompts as part of the current convergence loop" in reference_text
    assert "During an explicit skill-library review turn, only mutate the skill library" in reference_text
    assert "treat it as an interrupt" in reference_text
    assert "dispatch agents, or touch PR markers" in reference_text
    assert "stop with a concise report" in reference_text
    assert "Re-check installed↔repo skill state before consuming a fresh backstop" in reference_text
    assert "never use a PASS bound to the pre-refinement diff" in reference_text
    assert "Honor tool-scope limits during explicit memory/skill reviews" in reference_text
    assert "do not call repository, GitHub, terminal, search/read, delegation, todo/progress-tracking, marker, or PR tools" in reference_text
    assert "Do not consume pending Delivery Mode events during a skill-only interrupt" in reference_text
    assert "do not acknowledge, validate, dispatch around, write verdicts, or advance PR state" in reference_text
    assert "Let the interrupt reply be only the skill-library outcome" in reference_text
    assert "the final response should not include a Delivery Mode progress update" in reference_text
    assert "Skill-library review prompts supersede freshly-arrived Delivery Mode events for that turn" in reference_text
    assert "Do not summarize, validate, or consume the async event in the same reply" in reference_text
    assert "A skill-library review turn is not a Delivery Mode handoff" in reference_text
    assert "do not promise the next repository action in that same reply" in reference_text
    assert "Treat “be active” skill-library prompts as permission to improve skills, not to resume delivery" in reference_text
    assert "do not use the “be active” wording as permission to inspect repos" in reference_text
    assert "Avoid recursive micro-lessons from repeated skill-library interrupts" in reference_text
    assert "do not manufacture another near-duplicate rule just to be active" in reference_text
    assert "Handle PR-grind review-bot staleness explicitly after follow-up fixes" in reference_text
    assert "Resolve or reply to stale/false-positive threads" in reference_text
    assert "Do not declare completion while installed skill and repo source differ" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_pi_adapter_candidate_workflow_is_durable_skill_reference():
    assert PI_ADAPTER_CANDIDATE_WORKFLOW_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PI_ADAPTER_CANDIDATE_WORKFLOW_REFERENCE.read_text()

    assert "references/pi-adapter-candidate-workflow.md" in skill_text
    assert "Pi = Busdriver-compatible tool-harness / adapter candidate" in reference_text
    assert "`createAgentSession()` uses a ResourceLoader" in reference_text
    assert "not through the ResourceLoader itself" in reference_text
    assert "Launch Pi with built-in mutating tools disabled" in reference_text
    assert "Only after the in-repo schema/wrapper/smoke/contract tests pass" in reference_text
    assert "Pi is deferred route history, not current or preferred route metadata" in reference_text
    assert "agent_containment_and_credential_broker_unavailable" in reference_text
    assert "bd_bash` must be argv-only and allowlist-only" in reference_text
    assert "Any allowed `git status` form must inject `-c core.fsmonitor=false`" in reference_text
    assert "Any allowed `git diff` form must include `--no-ext-diff` and `--no-textconv`" in reference_text
    assert "hermes-worker-result/v0" in reference_text
    assert "avoid double Busdriver workflow" in reference_text
    assert "Use `pi --mode json`" in reference_text
    assert "gated draft runtime candidate" in reference_text
    assert "historical `hermes-busdriver-agent-draft → preflight → Pi adapter → postflight` fixture passed" in reference_text
    assert "Still not validated:" in reference_text
    assert "hermes-busdriver-agent-draft --agent custom" in reference_text
    assert "generic OpenCode fixture" in reference_text
    assert "configured-but-non-programmatic for production dispatch" in reference_text
    assert "OpenCode comparison remains optional historical evidence" in reference_text
    assert "by explicitly selecting `--agent summary`" not in reference_text
    assert "A formal `hermes-busdriver-gate preflight → Pi → postflight` launcher." not in reference_text
    assert "$SPACIOUS_RUNTIME_VOLUME/.hermes-runtime/pi-busdriver-smoke/" in reference_text
    assert "/Volumes/" not in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_pi_adapter_implementation_lessons_are_durable_skill_reference():
    assert PI_ADAPTER_IMPLEMENTATION_LESSONS_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PI_ADAPTER_IMPLEMENTATION_LESSONS_REFERENCE.read_text()

    assert "references/pi-adapter-implementation-lessons.md" in skill_text
    assert "Pi adapter implementation-specific workflow lessons" in skill_text
    assert "separate git worktree for the Pi adapter slice" in reference_text
    assert "Implementation belongs in the Hermes relay repo, not Pi upstream/source" in reference_text
    assert "HISTORICAL / SUPERSEDED" in "\n".join(reference_text.splitlines()[:5])
    assert "NON-PRODUCTION" in "\n".join(reference_text.splitlines()[:5])
    assert "docs/coding-workflow-authority-map.md" in "\n".join(reference_text.splitlines()[:5])
    assert "Codex lane = implementation-primary metadata and PR lead; production dispatch blocked." in reference_text
    assert "OpenCode+Go lane = secondary/fallback draft-only metadata; production dispatch blocked." in reference_text
    assert "Pi lane = deferred historical adapter metadata; not current, default, or preferred; production dispatch blocked." in reference_text
    assert "Pi lane    = preferred route metadata" not in reference_text
    assert "agent_containment_and_credential_broker_unavailable" in reference_text
    assert "A future successful Pi draft result would still be `needs_busdriver_review`" in reference_text
    assert "`bd_bash` should be argv-only and allowlist-only" in reference_text
    assert "`bd_write_draft` should enforce repo-root containment" in reference_text
    assert "Fake-Pi tests remain useful only as fixture provenance" in reference_text
    assert "parser and authority-negative production responses" in reference_text
    assert "do not prove production descendant containment, credential brokering, or dispatch authority" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_coding_workflow_authority_map_is_durable_skill_reference():
    assert CODING_WORKFLOW_AUTHORITY_MAP_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = CODING_WORKFLOW_AUTHORITY_MAP_REFERENCE.read_text()

    assert "references/coding-workflow-authority-map-v0.1.md" in skill_text
    assert "implementation.primary.current            = Codex metadata only" in reference_text
    assert "OpenCode + Go lane = secondary/fallback draft-only metadata; adapter contract verified in non-installed harnesses; production dispatch is policy-blocked." in reference_text
    assert "agent_containment_and_credential_broker_unavailable" in reference_text
    assert "Workers produce draft evidence; Hermes verifies evidence" in reference_text
    assert "Hermes must not commit a dirty tree unless every dirty path is classified" in reference_text
    assert "git -c core.fsmonitor=false status --porcelain=v1 --untracked-files=all" in reference_text
    assert "fsmonitor hook commands cannot execute" in reference_text
    assert "diff --no-ext-diff --no-textconv --name-only" in reference_text
    assert "external diff drivers/textconv filters cannot execute" in reference_text
    assert "Reviewer data-egress gate" in reference_text
    assert "A stronger model does not get more authority" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_every_busdriver_relay_reference_is_indexed_by_the_skill():
    skill_text = SKILL.read_text()

    missing = sorted(
        reference.name
        for reference in REFERENCE_DIR.glob("*.md")
        if f"references/{reference.name}" not in skill_text
    )

    assert missing == []


def test_active_skill_uses_authority_negative_role_resolution_semantics():
    skill_text = SKILL.read_text()
    resolver_text = (REFERENCE_DIR / "relay-role-resolver-lessons.md").read_text()
    role_status_text = (REFERENCE_DIR / "relay-role-status-integration-lessons.md").read_text()

    assert role_status_text.splitlines()[2] == (
        "> **CURRENT AUTHORITY-NEGATIVE — NON-PRODUCTION-DISPATCH.** Current policy authority: "
        "repository-root `docs/coding-workflow-authority-map.md`; all relay roles are metadata-only "
        "and production dispatch is blocked by `agent_containment_and_credential_broker_unavailable`."
    )
    assert "dispatch_allowed=false except the one safe resolved role" not in skill_text
    assert "resolved role is metadata-only" in skill_text
    assert "Root and nested `decision` `dispatch_allowed=false`" in role_status_text
    assert "exit `0` and `ok=true` validate resolved metadata" in role_status_text
    assert "Any `dispatch_allowed=true` claim must be rejected and production dispatch must remain blocked" in role_status_text
    assert "root `dispatch_allowed is true`" not in role_status_text
    assert "nested `decision.dispatch_allowed is true`" not in role_status_text
    assert "dispatch_allowed=<true only for safe resolved role>" not in resolver_text
    assert "`dispatch_allowed=false` for every role" in resolver_text


def test_skill_catalog_marks_superseded_role_policy_evidence_historical():
    catalog = next(
        line
        for line in SKILL.read_text().splitlines()
        if "Historical/superseded role-policy evidence" in line
    )
    qualifier = (
        "Historical/superseded role-policy evidence (not current routing; current authority: "
        "`references/coding-workflow-authority-map-v0.1.md`): "
    )
    historical = {
        "pi-adapter-implementation-lessons.md": "keep Pi target-state wording until proof passes",
        "relay-router-agent-role-split.md": "Codex primary fallback draft worker",
        "relay-router-role-policy-2026-07.md": "Codex→OpenCode implementation priority",
        "pr108-pi-authority-sync-delivery-lessons.md": "target-state Pi wording",
        "pr109-pi-adapter-final-pr-grind-lessons.md": "structured missing-Pi blocked outputs",
        "pr109-pi-adapter-review-rebase-lessons.md": "Pi adapter review/rebase delivery",
        "pr112-pi-default-dogfood-lessons.md": "Pi-default migration/dogfood",
        "relay-live-config-restoration-lessons.md": "Pi-first/Codex-review routes",
        "full-role-map-resolver-slice-lessons.md": "Zed manual IDE correction",
    }
    qualified_clauses = catalog.split(qualifier)[1:]

    for filename, stale_phrase in historical.items():
        assert catalog.count(f"references/{filename}") == 1
        assert any(
            f"references/{filename}" in clause and stale_phrase in clause
            for clause in qualified_clauses
        )


def test_skill_catalog_counts_active_and_historical_roadmap_rows_separately():
    skill_text = SKILL.read_text()

    assert "four active tasks plus one retained historical Pi-evidence row" in skill_text
    assert "five active roadmap tasks" not in skill_text


def test_pr106_expanded_skill_sync_pr_grind_lessons_are_durable_skill_reference():
    assert PR106_EXPANDED_SKILL_SYNC_PR_GRIND_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR106_EXPANDED_SKILL_SYNC_PR_GRIND_REFERENCE.read_text()

    assert "references/pr106-expanded-skill-sync-pr-grind-lessons.md" in skill_text
    assert "New reference files need durability tests in the same PR" in reference_text
    assert "Do not dismiss reviewer-bot “convention” comments" in reference_text
    assert "Patch installed and repo copies together for reviewer doc fixes" in reference_text
    assert "Resolved threads may need one more PR-grind poll" in reference_text
    assert "Use scoped git identity/signing env for final full-suite verification" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_pi_adapter_delivery_lessons_are_durable_skill_references():
    skill_text = SKILL.read_text()
    references = {
        PI_ADAPTER_ASYNC_REVIEW_FIX_REFERENCE: [
            "Wrapper artifact validation must enforce the checked-in schema",
            "`bd_read` must deny common secret paths",
            "After any reviewer-fix amend",
        ],
        PR108_PI_AUTHORITY_SYNC_REFERENCE: [
            "If the user confirms Pi as the chosen Busdriver-compatible tool-harness direction",
            "`bd_bash` being argv-only and no-shell is not enough",
            "`gh pr merge --squash --delete-branch` can perform the remote squash merge successfully",
        ],
        PR109_PI_ADAPTER_REVIEW_REBASE_REFERENCE: [
            "Blocked artifacts must propagate as blocked",
            "`ours` / `HEAD` = the branch being rebased onto",
            "stale pseudo-ref such as `REBASE_HEAD`",
        ],
        PR109_PI_ADAPTER_FINAL_PR_GRIND_REFERENCE: [
            "Forward `--scope-exclude`",
            "Suppress project-local Pi system prompts explicitly",
            "If `gh pr merge --squash --delete-branch` prints a local git/worktree error",
        ],
    }

    for reference, expected_phrases in references.items():
        assert reference.exists()
        assert f"references/{reference.name}" in skill_text
        reference_text = reference.read_text()
        for phrase in expected_phrases:
            assert phrase in reference_text
        for leaked_path in PRIVATE_PATH_LEAKS:
            assert leaked_path not in reference_text
        assert "/Volumes/" not in reference_text


def test_full_role_map_and_live_config_lessons_are_durable_skill_references():
    skill_text = SKILL.read_text(encoding="utf-8")
    references = {
        FULL_ROLE_MAP_DISPATCHABILITY_REFERENCE: [
            "Resolver-ready is not the same as dispatchable",
            "OpenCode fallback/comparison roles stay non-dispatchable until the complete production safety proof exists",
            "agent_containment_and_credential_broker_unavailable",
            "After repo skill-source merges, check installed skill drift",
        ],
        OPENCODE_FALLBACK_PROOF_AUDIT_REFERENCE: [
            "OpenCode fallback proof audit lessons",
            "Requirements before any future promotion",
            "every reusable authority flag false",
            "configured fallback/comparison **route**, not a production programmatic lane",
        ],
        GATED_FINALIZATION_EXECUTOR_OPENCODE_REFERENCE: [
            "Gated finalization executor + OpenCode fallback lessons",
            "per-operation authority surface",
            "Do not raw-write `.claude/*` trusted markers",
            "update all status surfaces in the same slice",
        ],
        FULL_ROLE_MAP_RESOLVER_SLICE_REFERENCE: [
            "Do not stop at resolver-known subset restoration",
            "relay.impl.primary = pi",
            "relay.ide.manual = zed",
            "Create a fresh follow-up worktree/branch from the saved/live PR base branch",
        ],
        PR112_PI_DEFAULT_DOGFOOD_REFERENCE: [
            "Pi-default is a policy migration",
            "Preserve custom test/advanced command behavior",
            "Balanced planning must track default implementation policy",
            "Latest-head PR-grind still wins",
        ],
        RELAY_LIVE_CONFIG_RESTORATION_REFERENCE: [
            "Separate target policy from live resolver state",
            "Check the live config before answering model/agent questions",
            "Full role-map resolver state after PR #113",
            "Dispatchability is still separate from resolver readiness",
            "full 19-role resolver inventory",
        ],
    }

    for reference, expected_phrases in references.items():
        assert reference.exists()
        assert f"references/{reference.name}" in skill_text
        reference_text = reference.read_text(encoding="utf-8")
        for phrase in expected_phrases:
            assert phrase in reference_text
        for leaked_path in PRIVATE_PATH_LEAKS:
            assert leaked_path not in reference_text
        assert "/Volumes/" not in reference_text


def test_pr67_skill_sync_review_fix_lessons_are_durable_skill_reference():
    assert PR67_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR67_REFERENCE.read_text()

    assert "references/pr67-skill-sync-review-fix-lessons.md" in skill_text
    assert "Do not weaken fail-closed helper semantics in lessons" in reference_text
    assert "After PR creation, prefer follow-up commits over amend" in reference_text
    assert "Restart all latest-head evidence after a follow-up push" in reference_text
    assert "Carry the live PR base branch through cleanup lessons" in reference_text
    assert "Do not hard-code `main` or `main...origin/main` in reusable cleanup/final-audit guidance" in reference_text
    assert "switch back to `main`" not in reference_text
    assert "saved base branch against its upstream" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_adr0005_authority_source_status_lessons_are_durable_skill_reference():
    assert ADR0005_AUTHORITY_SOURCE_STATUS_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = ADR0005_AUTHORITY_SOURCE_STATUS_REFERENCE.read_text()

    assert "ADR0005 authority-source status rows" in skill_text
    assert "references/adr0005-authority-source-status-lessons.md" in skill_text
    assert "Authority-source rows are status rows too" in reference_text
    assert "retired: false" in reference_text
    assert "implemented: false" in reference_text
    assert "Preserve `required_authority_sources` exactly" in reference_text
    assert "Recursive false-authority tests should include new rows" in reference_text
    assert "PR-grind feedback can be schema consistency" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text
    assert "/Volumes/" not in reference_text


def test_pr118_skill_sync_delivery_lessons_are_durable_skill_reference():
    assert PR118_SKILL_SYNC_DELIVERY_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR118_SKILL_SYNC_DELIVERY_REFERENCE.read_text()

    assert "PR118-style skill-source sync slices" in skill_text
    assert "references/pr118-skill-sync-delivery-lessons.md" in skill_text
    assert "Durability tests must pin the intended SKILL entry" in reference_text
    assert "Whole-skill compare comes before and after repo sync" in reference_text
    assert "Dirty-branch smoke can be phase-inappropriate" in reference_text
    assert "Use normal follow-up commits for PR-grind reviewer fixes" in reference_text
    assert "Branch-keyed locks may need temporary branch recreation after squash merge" in reference_text
    assert "Re-read live PR state before mutating around reviewer-bot rate limits" in reference_text
    assert "CodeRabbit rate-limit comment" in reference_text
    assert "Reusable checklist wording must not hard-code `main`" in reference_text
    assert "A nonzero `gh pr merge` exit can still leave the PR merged and the base synced" in reference_text
    assert "Re-read live PR state (`gh pr view` merge commit/state)" in reference_text
    assert "Phase-0 clean synced PR base" in reference_text
    assert "Phase-0 clean main" not in reference_text
    assert "main...origin/main" not in reference_text
    assert "switch back to `main`" not in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text
    assert "/Volumes/" not in reference_text


def test_lock_cli_usage_pitfalls_lessons_are_durable_skill_reference():
    assert LOCK_CLI_USAGE_PITFALLS_REFERENCE.exists()
    skill_text = SKILL.read_text(encoding="utf-8")
    reference_text = LOCK_CLI_USAGE_PITFALLS_REFERENCE.read_text(encoding="utf-8")

    assert "references/lock-cli-usage-pitfalls.md" in skill_text
    assert "relay lock helper pitfalls" in skill_text
    assert "Release is branch-keyed through the live repo identity" in reference_text
    assert "Do not assume all lock subcommands accept the same flags" in reference_text
    assert "Acquire output stores the token at the top level and inside `lock`" in reference_text
    assert "Verify lock cleanup from the actual status payload" in reference_text
    assert "require lock status count=0" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text
    assert "/Volumes/" not in reference_text


def test_pr68_late_async_test_followup_lessons_are_durable_skill_reference():
    assert PR68_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR68_REFERENCE.read_text()

    assert "references/pr68-late-async-test-followup-lessons.md" in skill_text
    assert "Classify late async results against current merged state" in reference_text
    assert "Convert cheap test-only non-blocking suggestions into tiny follow-up PRs" in reference_text
    assert "Keep follow-up scope minimal" in reference_text
    assert "Remote branch deletion can already be done by GitHub merge" in reference_text
    assert "remote ref does not exist" in reference_text
    assert "fetch --prune" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_read_only_skill_sync_audit_lessons_are_durable_skill_reference():
    assert READ_ONLY_SKILL_SYNC_AUDIT_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = READ_ONLY_SKILL_SYNC_AUDIT_REFERENCE.read_text()

    assert "references/read-only-skill-sync-audit-lessons.md" in skill_text
    assert "Stay strictly read-only" in reference_text
    assert "Confirm the selected slice from live drift" in reference_text
    assert "Patch installed and repo copies to the same sanitized text" in reference_text
    assert "avoid adding the raw forbidden sentinel strings in new test constants" in reference_text
    assert "include that sanitized reference in the same repo sync" in reference_text
    assert "Validate concurrent skill-sync WIP without taking ownership" in reference_text
    assert "Distinguish pre-WIP failures that prove the drift from post-WIP passes" in reference_text
    assert "run a final whole-skill installed-vs-repo comparison" in reference_text
    assert "classify it as a blocker or explicit scope decision" in reference_text
    assert "Preserve authority boundaries" in reference_text
    assert "CURRENT_STATUS follow-up after merge" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_roadmap_readonly_audit_lessons_are_durable_skill_reference():
    assert ROADMAP_READONLY_AUDIT_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = ROADMAP_READONLY_AUDIT_REFERENCE.read_text()

    assert "references/roadmap-readonly-audit-lessons.md" in skill_text
    assert "completed contract, policy-blocked finalization" in reference_text
    assert "remaining_work_count=5" in reference_text
    assert "capability_allowed_count=0" in reference_text
    assert "Preserve `git status --short` leading whitespace" in reference_text
    assert "OpenCode remains a candidate/status slice" in reference_text
    assert "non_codex_agent_enablement_allowed=false" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_periodic_disk_cleanup_cron_lessons_are_durable_skill_reference():
    assert PERIODIC_DISK_CLEANUP_CRON_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PERIODIC_DISK_CLEANUP_CRON_REFERENCE.read_text()

    assert "references/periodic-disk-cleanup-cron-lessons.md" in skill_text
    assert "script-only cron job" in reference_text
    assert "no_agent=true" in reference_text
    assert "empty stdout means silent/no delivery" in reference_text
    assert "Do not automatically clean other agents' durable state" in reference_text
    assert "Report local Time Machine/APFS snapshots as a hint only" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_pr98_roadmap_brief_cleanup_lessons_are_durable_skill_reference():
    assert PR98_ROADMAP_BRIEF_CLEANUP_REFERENCE.exists()
    skill_text = SKILL.read_text()
    reference_text = PR98_ROADMAP_BRIEF_CLEANUP_REFERENCE.read_text()

    assert "references/pr98-roadmap-brief-cleanup-lessons.md" in skill_text
    assert "Compact status helpers must fail closed on unverified inputs" in reference_text
    assert "Strip inherited `GIT_*` identity/path variables" in reference_text
    assert "status.showUntrackedFiles=all" in reference_text
    assert "Preserve the two-column porcelain status format" in reference_text
    assert "missing=N extra=N diffs=N" in reference_text
    assert "right reconciliation direction" in reference_text
    assert "restart from the latest head" in reference_text
    assert "script-only `no_agent=true` cron" in reference_text
    for leaked_path in PRIVATE_PATH_LEAKS:
        assert leaked_path not in reference_text


def test_idle_and_convergence_lessons_are_durable_skill_references():
    skill_text = SKILL.read_text()
    references = {
        IDLE_CLEAN_FINALIZATION_READINESS_REFERENCE: [
            "distinguish **no candidate** from **blocked candidate**",
            "stale-litmus detail in `delivery_status.decision.blockers`",
            "Leave the dirty tree for main Hermes/operator verification/finalization",
        ],
        IDLE_FINALIZATION_READINESS_STATUS_AUDIT_REFERENCE: [
            "distinguish **no finalization candidate exists** from **a candidate exists but is blocked**",
            "Dirty draft changes with stale/blocked litmus evidence must remain `blocked`",
            "PR/merge paths with stale/non-clean evidence must remain blocked",
        ],
        SKILL_SYNC_CURRENT_STATUS_CONVERGENCE_REFERENCE: [
            "Run a whole-skill installed-vs-repo comparison",
            "If final-audit skill maintenance creates a new installed-only class-level reference",
            "sync it to repo with durability assertions, then refresh CURRENT_STATUS against the latest merged head",
            "For a user-explicit safe continuation slice that says to leave the working tree dirty for main Hermes",
            "watch the focused test fail against the stale repo source",
            "Do not commit, push, open a PR, merge, or touch `docs/CURRENT_STATUS.md` unless the user explicitly changes scope",
            "Make `docs/CURRENT_STATUS.md` the last convergence slice whenever possible",
            "Run `git fetch --prune` during merge cleanup before the completion audit",
            "no open PRs, relay topic branches, or stale remote-tracking topic branches remain",
            "CURRENT_STATUS required fresh tokens are present and stale tokens are absent",
            "claude-mem is updated when configured/approved",
        ],
        PR78_SKILL_SYNC_PRE_PR_REFERENCE: [
            "Do a final whole-skill compare after subagents return and after any main-Hermes patch",
            "Use the installed plugin version for smoke/status evidence",
            "Pre-PR dual-voice sequence is still mandatory after commit",
            "After PR reviewer fixes, restart latest-head evidence",
            "Treat reviewer-bot “trivial” comments as blocking when PR-grind classifies them as actionable",
            "If skill maintenance during delivery creates a new installed-only reference, sync it in the same PR before status refresh",
        ],
        POST_MERGE_SKILL_DRIFT_BEFORE_STATUS_REFERENCE: [
            "After every skill-sync PR merge, return to the synced base branch and run the whole-skill installed-vs-repo comparison again",
            "Only after installed skill and repo source compare clean should `docs/CURRENT_STATUS.md` become the last evidence-only refresh slice",
            "hermes-busdriver-litmus-status` may report `branch_diff_hash_unavailable: empty diff`",
            "hermes-busdriver-finalization-contract-status` is currently a repo-cwd helper with no `--repo` option",
            "Any commit made after an async PR backstop verdict invalidates that verdict",
            "Never persist a backstop JSON whose `reviewed_diff_hash` belongs to a prior HEAD",
            "Do not refresh `CURRENT_STATUS` between two skill-sync PRs",
        ],
    }

    for reference, expected_phrases in references.items():
        assert reference.exists()
        assert f"references/{reference.name}" in skill_text
        reference_text = reference.read_text()
        for phrase in expected_phrases:
            assert phrase in reference_text
        for leaked_path in PRIVATE_PATH_LEAKS:
            assert leaked_path not in reference_text
        if reference == PR78_SKILL_SYNC_PRE_PR_REFERENCE:
            assert "/Volumes/" not in reference_text
            assert "~/.claude/plugins" not in reference_text


def test_git_observation_skill_keeps_submodules_visible():
    sources = (
        SKILL,
        REFERENCE_DIR / "git-observation-sandbox-lessons.md",
    )
    for source in sources:
        text = source.read_text()
        assert "--ignore-submodules=none" in text
        assert "--ignore-submodules=all" not in text
