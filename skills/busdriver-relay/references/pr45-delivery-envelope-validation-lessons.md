> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`.

# PR45 delivery-status envelope validation lessons

Session lesson from continuing after PR44: the next strict-helper-evidence gap was not inside nested `litmus_status` evidence, but at the boundary where `hermes-busdriver-finalization-readiness` consumes the whole `hermes-busdriver-delivery-status` child envelope.

## Bug pattern

`finalization-readiness` previously treated the child delivery-status result as trustworthy with a truthiness check like `delivery.get("ok")`. That allowed malformed or unsafe child envelopes to reach `ready_for_commit_or_pr_handoff`, including:

- wrong delivery-status schema with `ok=True`
- `read_only=False` with `ok=True`
- non-boolean truthy `ok` such as `"true"`

## Durable fix pattern

When a read-only wrapper consumes another helper's JSON envelope, validate the helper envelope before using its decision fields:

- expected child schema exactly matches the producer contract
- `read_only is True`
- `ok` is a boolean, not a truthy/falsy string or other primitive
- invalid envelope adds a distinct blocker such as `delivery_status_schema_invalid`
- top-level wrapper `ok` also requires the child envelope schema to be valid
- authority/finalization flags remain false recursively

Delivery-status itself should advertise top-level `read_only: true` so downstream wrappers can verify the non-mutating contract explicitly.

## TDD regression recipe

1. Add a RED test that calls the wrapper readiness function with a minimal otherwise-ready payload, then overrides the child delivery-status envelope with:
   - wrong schema
   - `read_only=False`
   - `ok="true"`
2. Verify the RED test fails because readiness incorrectly reports ready.
3. Add the smallest production validator and blocker.
4. Run the focused regression, related contract tests, and full smoke.

Expected assertions:

- `ready is False`
- `status == "blocked"`
- `delivery_status_schema_invalid` is in blockers
- all commit/push/PR/merge/deploy/release/publish/marker/finalization authority flags remain false

## Reviewer feedback pitfall

A reviewer may flag duplicated schema literals between executable helper scripts. Avoid importing executable scripts just to share constants if that creates coupling or side effects. A minimal acceptable fix is a clear cross-reference comment next to the duplicate contract literal, for example:

```python
# Keep synchronized with scripts/hermes-busdriver-delivery-status SCHEMA.
# The sibling is an executable helper, so validate by contract literal here rather than importing it.
DELIVERY_STATUS_SCHEMA = "hermes-busdriver-delivery-status/v0"
```

Use a shared module only if the project already has one or the drift risk justifies the extra abstraction.

## Verification observed

The safe delivery loop for this kind of slice was:

- RED: focused new regression failed (`3 failed`) before production fix.
- GREEN focused: regression and adjacent checks passed.
- Related suites: delivery-status + finalization-readiness contract tests passed.
- Full smoke: `hermes-busdriver-smoke` passed with full contract suite and py_compile.
- PR-grind after reviewer fix: latest head clean before merge.
- Post-merge smoke: full contract suite and py_compile still passed; base branch clean/synced.
