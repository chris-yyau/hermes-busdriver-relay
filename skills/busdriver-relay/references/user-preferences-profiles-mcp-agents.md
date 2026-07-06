# User Preferences for busdriver-relay Coding Tasks

## Hermes Profile vs Relay Skill Boundary
- `busdriver-relay` is a **thin relay skill**, not a Hermes profile.
- It loads into the user's main/default Hermes profile.
- When the user asks \"is busdriver relay the main profile?\" or \"do we need a new coding profile?\": answer **no**.
- Only consider a dedicated profile later if the user wants complete isolation (separate config, memory, plugins, model defaults) for the relay layer.
- Keep answers short and direct; the relay remains a capability on the main profile.

## Pi-default Active Scope
- Use **Pi** as the default constrained implementation draft lane; keep **Codex** only as explicit fallback when Pi is blocked or unsuited.
- Defer OpenCode, Droid, Agy, Grok.
- Do not expand surface (CLI, smoke, docs, examples) for other agents without fresh confirmation.
- Reason: avoid duplicating agent-side Busdriver plugins (e.g. OpenCode) and keep the relay thin.

## AGENTS.md for Coding Work
- For coding tasks under this skill, prioritize reading `~/.hermes/AGENTS.md` at the start of implementation.
- Apply its rules: Think Before Coding (surface assumptions), Simplicity First, Surgical Changes (minimal traceable edits), Goal-Driven Execution (verifiable goals).

## Direct remote / config action preference
When the user says "你拿key去呀", "你去改呀", "just go fix the .env", or "I already filled the key in Hermes":
- Immediately use terminal/SSH to edit the remote file (pull key from Hermes config if needed).
- Do **not** leave placeholders, re-explain separation, or ask for the key again.
- Apply + restart + verify in one go.
- This avoids frustration signals. Applies to Honcho .env, remote configs, and similar relay tasks.

## claude-mem MCP (query + push)
- Query observations, sessions, context via MCP tools or direct search.
- For push (Hermes coding results visible to Claude Code): see main SKILL.md and `references/claude-mem-push.md`.
- Explicit log after significant Hermes work; use agent_type="hermes".
- Complements Hermes native memory (Hindsight) for cross-agent continuity.
- Backend typically at `~/.claude-mem/chroma` + sqlite observations table.

## Three memory systems (Hindsight + Honcho + claude-mem)
- Hindsight: Hermes automatic provider (technical + session memory).
- Honcho: manual user modeling / conclude / dialectic (called explicitly via honcho-tools).
- claude-mem: primarily Claude Code observations; Hermes pushes explicitly for visibility on Claude side.
- Never set Honcho or claude-mem as Hermes' global `memory.provider`.

## Related
See main SKILL.md sections on MCP/Plugin Boundary, Current User Scope Policy, Execution Seam Classification, and claude-mem push guidance.
