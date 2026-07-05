# Pi adapter-candidate workflow lesson

## Trigger

Use this note when discussing whether Pi should be added to, replace, or compete with OpenCode/Codex in Hermes↔Busdriver relay work.

## User correction captured

When the user proposes a role/pipeline change as a question, do **not** immediately write memory or answer from stale policy. First verify the concrete capability claim when it is checkable. In this session, the user asked about adding Pi because it can adjust its own tools; Hermes first saved memory and answered hypothetically, then the user corrected that Hermes should have checked.

## Confirmed Pi capability shape

Pi is not merely another coding model. It is an agent harness with a configurable tool layer:

- CLI supports `--extension/-e` for extension files.
- CLI supports disabling/restricting tools: `--no-tools`, `--no-builtin-tools`, `--tools`, `--exclude-tools`.
- Extensions can register custom tools with `pi.registerTool(...)`.
- Extensions can intercept lifecycle/tool events.
- Built-in tools such as `read` can be overridden, enabling access control, logging/auditing, sandboxing, or remote/tool-wrapper routing.
- SDK/resource-loader paths support custom extensions, skills, prompts, tools, sessions, and programmatic embedding.

This makes Pi a plausible **Busdriver-shaped tool harness** candidate: it can run with built-ins disabled and expose only wrapper tools that map to Busdriver/Hermes relay gates, state-dir policy, scope policy, and artifact contracts.

## Revised role interpretation

Do not frame Pi as an immediate Busdriver authority or direct replacement for Codex. The safer role is:

```text
Pi = Busdriver-compatible tool-harness / adapter candidate
```

Pi may challenge OpenCode specifically in the **secondary adapter / tool-shape** role, because Pi's tool layer may be easier to reshape around Busdriver semantics. But OpenCode should not be removed immediately because the user already has an OpenCode Busdriver plugin pipeline and Chinese-model agent/tool lane.

Recommended interim map:

```text
implementation.primary        = Codex
implementation.secondary      = OpenCode          # existing candidate / plugin lane
adapter.tool_harness.candidate = Pi               # new challenger for Busdriver-shaped tools
Busdriver/Claude              = authority
Hermes                        = router/operator/verifier
```

If Pi wins validation, a future policy may become:

```text
implementation.primary       = Codex
adapter.tool_harness.primary = Pi
opencode                     = tertiary / Chinese-model / legacy-plugin lane
```

## Validation workflow before promoting Pi

1. **Read-only Pi smoke**
   - Launch Pi with built-in mutating tools disabled.
   - Load a Busdriver-relay extension exposing only safe read/status/Phase-0 tools.
   - Verify it can inspect repo/gate/state-dir status.
   - Verify it cannot mutate files, commit, push, PR, merge, or write Busdriver markers.

2. **Draft-only Pi smoke**
   - Wrap all write/edit/bash-like actions through Busdriver/Hermes relay preflight/postflight wrappers.
   - Keep commit/push/PR/merge/marker writes blocked.
   - Require structured artifact output ending in `needs_busdriver_review`.
   - Hermes reconciles actual git diff/status against Pi's claims.

3. **Pi vs OpenCode comparison**
   - Run the same small adapter task through OpenCode's existing plugin lane and Pi's custom-tool lane.
   - Compare tool controllability, gate parity, state-dir handling, artifact quality, prevention of finalization escape, and draft quality.

Only after these smokes should Pi replace OpenCode in any formal secondary adapter role.

## Hermes responsibility in this workflow

Hermes should remain the router/operator/verifier:

- classify the task;
- run Phase 0 live discovery;
- choose Codex/Pi/OpenCode/reviewer routes;
- build explicit handoff contracts;
- prevent workers from becoming authority;
- verify returned artifacts against live repo state;
- organize Busdriver/Claude authority review or explicit Delivery Mode finalization.

Pi provides adjustable tools; Hermes is responsible for ensuring those tools cannot exceed Busdriver-compatible boundaries.