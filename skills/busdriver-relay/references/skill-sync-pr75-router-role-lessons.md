> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# Skill-Sync PR75 Router Role Lessons

Use when syncing installed Hermes `busdriver-relay` skill references back into the repo and the drift includes relay-router / role-policy guidance.

## What happened

- A clean-main continuation found repo-vs-installed skill drift plus stale `docs/CURRENT_STATUS.md` evidence.
- The skill-sync slice copied installed-only router-role references into the repo and added durable skill-reference tests.
- PR feedback exposed three important documentation-contract pitfalls:
  1. A sample relay config used `relay.pr.backstop=["codex"]` while the refined role policy says PR backstop is `claude-code`.
  2. Before the full-role-map slice, samples with router roles (`relay.impl.secondary`, `relay.review.fast`, etc.) had to be labelled non-copyable because the resolver did not recognize them yet.
  3. `avoid_coding_agent_for_review=true` can make review/backstop roles degrade if they select the current `coding_agent`; implementation roles such as `relay.impl.primary=["pi"]` are exempt from review-independence degradation.
- Reviewer comments from older heads were auto-marked addressed, but a new current-head Codex review comment still blocked PR-grind until the sample was made resolver-ready.

## Durable workflow

1. **Sync installed and repo copies together.** If you patch an installed-skill reference during PR feedback, patch the repo copy in the same logical change before claiming diff clean.
2. **Make copyable config snippets executable against today's helper contracts.** For `hermes-busdriver-relay-role`, verify the sample config with current recognized roles, not just with desired future roles.
3. **Keep copyable samples aligned with the current first-class role inventory.** `relay.impl.*`, `relay.review.*`, `relay.blueprint.*`, `relay.pr.*`, `relay.council.*`, `relay.ide.manual`, and `relay.expert_witness.ultraoracle` are now resolver-ready; newly invented roles still need explicit inventory/tests before appearing as copyable config.
4. **Check resolver implications of independence flags.** `avoid_coding_agent_for_review=true` protects review/backstop roles from selecting the current coding agent while allowing implementation roles such as `relay.impl.primary=["pi"]` to match `coding_agent="pi"`.
5. **After every fix push, restart latest-head PR-grind.** Do not rely on older reviewer comments marked addressed; inspect current-head review comments and rerun the loop until the latest PR head is clean.
6. **After a skill-sync merge, continue with the docs/status convergence slice.** Do not stop merely because skill sync merged if `docs/CURRENT_STATUS.md` still references an older PR/head.

## Verification pattern

```text
repo-vs-installed skill diff
→ copy/sanitize installed-only references into repo
→ add durable reference tests for key phrases, private-path leak checks, and resolver-ready sample claims
→ run focused skill-reference tests
→ compare repo vs installed skill byte-for-byte
→ run resolver probes for copyable config snippets
→ full contract tests + smoke when clean
→ PR / latest-head PR-grind / merge
→ final audit then CURRENT_STATUS refresh if stale
```

## Pitfalls

- A PR-grind `needs_fix` after checks pass can be caused by a single current-head review comment, even when older Cubic/CodeRabbit comments say addressed.
- A documentation-only config snippet can still be a contract bug if copying it into `--relay-config` makes the resolver fail or degrade.
- Do not leave installed skill and repo skill different after locally patching installed-skill references during a reviewer-fix round.
