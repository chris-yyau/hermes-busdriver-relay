# Frozen review hardening: auth isolation, semantic docs, and runtime identity

Use this reference when an exact frozen candidate passes its current suite but an independent review challenges hermeticity, capability wording, or trusted-runtime coverage.

## 1. Preserve frozen generations

- A blocking finding makes that frozen generation `BLOCKED`; do not edit its manifest, patch, tar, verifier, or rebuilt candidate.
- Save the main disposition against the exact manifest digest and candidate tree.
- Clone the frozen source into a new generation, add a RED regression, make it GREEN, rerun the full isolated suite, then issue a new manifest/digest/tree.
- Distinguish a reviewer-lane closure failure (missing end verifier, report not saved, runner unavailable) from a code finding. The former prevents `CLEAN`; the latter still requires a new generation when independently reproduced.

## 2. Hermetic credential fixtures

Synthetic HOME/config is insufficient if credential environment variables remain inherited.

For GitHub-facing tests, clear at fixture setup:

```text
GH_TOKEN
GITHUB_TOKEN
GH_ENTERPRISE_TOKEN
GITHUB_ENTERPRISE_TOKEN
GH_CONFIG_DIR
```

Then:

1. Inject synthetic credentials only inside tests that explicitly exercise credential handling, after the autouse fixture has run.
2. Add a helper-level regression that seeds every ambient variant and proves the fixture removes them.
3. Add an actual autouse-presence node and launch it from an outer process with all sentinels set; checking only a normally-clean CI environment is vacuous.
4. Run the full suite under a fresh HOME and isolated git config without real secrets.

General rule: isolate both file-backed config and precedence-winning environment variables.

## 3. Active documentation is a policy surface

A blocker token appearing somewhere in a file does not neutralize an enabled-capability claim elsewhere in the same file.

Audit all active/current guidance together:

- README and CURRENT_STATUS;
- accepted/target-state ADRs;
- executable docstrings/help text;
- the umbrella SKILL.md;
- every reference that SKILL.md presents as current guidance.

Historical adapter/smoke evidence must be labeled non-installed provenance and every procedural paragraph must agree with the current production blocker. A banner alone is not enough if later sections still say “enabled”, “may launch”, or prescribe a real-agent workflow.

Do not use only an exact-string blacklist. Add a semantic contract that:

1. detects production/current activation verbs such as launch, dispatch, execute, run, perform, enabled, and verified;
2. accepts the statement only when the same statement is explicitly blocked, false, non-programmatic, historical, target-state, superseded, or non-installed;
3. includes reviewer-style paraphrase mutants, for example “Production launches agents for scoped drafts” and “Production performs real-agent verification”.

Keep specific phrase contracts for important canonical wording, but use semantic mutants to prevent trivial paraphrase bypass.

## 4. Trusted runtime identity and ownership scope

A manifest that hashes executables and helper scripts is incomplete if the production consumer identity or owner entrypoints are outside its contract.

Bind and test together:

- upstream Busdriver commit;
- package/version at that pinned commit;
- authenticated external executables and plugin files;
- embedded helper digests;
- every side-effect-capable or agent-facing production entrypoint.

Production materialization must reject a pinned commit whose package identity/version is unexpected. Contract tests must mutate commit/version, omit an owner, and change an owner digest; each mutation must fail.

Use a separate `production_entrypoints` inventory when appropriate. This makes ownership scope explicit without implying that a listed, policy-blocked launcher is dispatchable. Avoid self-referential hash cycles: the manifest may hash an entrypoint that embeds subordinate pins, but do not embed the manifest's own digest back into that entrypoint unless the design has a deliberate cycle-breaking mechanism.

## 5. Verification sequence

For the repaired generation:

1. Capture RED failures for every reproduced finding.
2. Run focused GREEN tests and the complete affected modules.
3. Run a full isolated-HOME suite from source.
4. Freeze a deterministic manifest/patch/source snapshot and pin expected record counts, base refs, branch, candidate tree, and manifest digest in the verifier.
5. Rebuild only from frozen artifacts and rerun the full suite plus trusted-runtime/static checks.
6. Run main start/end/final verifier lanes, make artifacts read-only, then dispatch independent review lanes with explicit report paths and a known pytest interpreter.
7. Require every lane to save a report before optional exhaustive probes so a tool ceiling cannot erase the verdict.

Any byte edit restarts this sequence under a new frozen generation.
