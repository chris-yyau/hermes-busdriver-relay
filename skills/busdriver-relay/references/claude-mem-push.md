# Pushing Hermes Work to claude-mem

Use when the user wants Hermes coding / tool actions visible inside Claude Code sessions (claude-mem observations).

## Core Principle
claude-mem is **not** fed automatically by Hermes. It is populated by Claude Code hooks + explicit writes. Hermes (Hindsight) stays the automatic provider. Push only on explicit request or at end of significant coding tasks.

## When to Push
- User says "要的", "push to claude-mem", "讓 claude code 記得 Hermes 做了什麼".
- After a block of Hermes coding work (edits, terminal changes, design decisions) that should be visible on the Claude side.
- Use type "change", "discovery", or "decision".

## Discovery Steps (always JIT)
1. Find a valid memory_session_id for the project:
   ```bash
   sqlite3 ~/.claude-mem/claude-mem.db "
     SELECT memory_session_id, project 
     FROM sdk_sessions 
     WHERE project LIKE '%busdriver%' OR project = 'busdriver'
     ORDER BY rowid DESC LIMIT 1;
   "
   ```
2. Inspect recent observations for style:
   ```bash
   sqlite3 ~/.claude-mem/claude-mem.db "
     SELECT id, type, title, narrative, agent_type, files_modified 
     FROM observations 
     WHERE project='busdriver' 
     ORDER BY created_at DESC LIMIT 2;
   "
   ```

## Recommended Insert Pattern (Python, via Hermes terminal)
```python
import sqlite3, time, json
from datetime import datetime, timezone

conn = sqlite3.connect("/Users/vfrvndtt/.claude-mem/claude-mem.db")
cur = conn.cursor()

sid = "2e79ad84-604f-486e-b046-21c7cad8e65d"  # from discovery
proj = "busdriver"
now = datetime.now(timezone.utc).isoformat()
epoch = int(time.time())

cur.execute("""
INSERT INTO observations 
(memory_session_id, project, type, title, narrative, concepts, 
 files_modified, agent_type, agent_id, created_at, created_at_epoch)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    sid, proj, "change",
    "Hermes: <short title of work>",
    "<detailed narrative of what Hermes changed/decided>",
    json.dumps(["hermes", "coding", "relay"]),
    json.dumps(["path/to/file1.py", "config.yml"]),
    "hermes", "hermes-agent",
    now, epoch
))
conn.commit()
print("Logged to claude-mem, id=", cur.lastrowid)
conn.close()
```

## Key Fields
- `type`: change | discovery | decision | bugfix | feature | refactor
- `agent_type`: "hermes" (distinguishes from Claude Code native)
- `agent_id`: "hermes-agent" or similar
- `files_modified`: list of paths touched by Hermes
- `narrative`: concise but sufficient for Claude Code to understand context
- `concepts`: tags that help retrieval (include "hermes")

## MCP Path (preferred when available)
Confirm with `hermes mcp list` (claude-mem ✓ enabled). 
If a write/create observation tool is exposed (e.g. claude_mem_add_observation), prefer calling the MCP tool over raw DB. Fall back to the Python pattern above.

## Pitfalls
- Do not auto-push on every tool call — too noisy. Push at natural task boundaries.
- Wrong session_id or project → observation lands in the wrong context.
- Forgetting agent_type="hermes" makes it look like native Claude work.
- After insert, chroma may need time or manual sync for semantic search; FTS is immediate.

See main SKILL.md claude-mem section and honcho-tools for the three-memory-system separation (Hindsight auto, Honcho manual user modeling, claude-mem explicit for Claude Code visibility).
