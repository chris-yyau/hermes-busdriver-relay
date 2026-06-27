# June 2026 PR Reviewer Quality Evaluation

## Scope

- Window: 2026-06-01 through 2026-06-30 (requested reporting period preserved from the supplied evaluation report; this document records that report rather than recalculating live metrics at save time).
- Owners: `chris-yyau` and `Dive-And-Dev`.
- Total PRs reviewed: 218 (`chris-yyau`: 77, `Dive-And-Dev`: 141).
- Reviewers evaluated: CodeRabbit, cubic, Codex, Cursor, Devin.

## Reviewer summary

| Reviewer | PRs | Events | Check/status | Median latency | Unresolved thread comments | Score | Relay interpretation |
|---|---:|---:|---:|---:|---:|---:|---|
| CodeRabbit | 205 | 451 | 205 | 0.09h | 29 | 7.5 | Broad and fast. Treat rate-limit / no-review as incomplete, not clean. |
| cubic | 171 | 464 | 154 | 0.20h | 27 | 6.8 | Structured advisory reviewer. Only high-confidence live P1/P2 findings should block. |
| Codex | 54 | 339 | 0 | 0.77h | 83 | 8.0 | Best deep blocker. Block only live unresolved P1/P2 findings; respect resolved, addressed-by-design, and stale semantics. |
| Devin | 12 | 139 | 12 | 1.30h | 14 | 6.0 | Verification/advisory. Status success is not a clean ack; block only live unresolved inline `BUG` / `🚩` findings. |
| Cursor | 57 | 52 | 55 | 0.43h | 1 | 7.0 | Lower volume but useful for specific secondary bug blockers. |

## Representative examples

### CodeRabbit

Good findings:

- `Dive-And-Dev/chrisyau.me#137`: shell/script workflow risk — <https://github.com/Dive-And-Dev/chrisyau.me/pull/137#discussion_r3362708212>
- `Dive-And-Dev/jikdak#162`: slug mismatch — <https://github.com/Dive-And-Dev/jikdak/pull/162#discussion_r3340408200>

Problem case:

- `chris-yyau/busdriver#241`: rate-limit warning — <https://github.com/chris-yyau/busdriver/pull/241#issuecomment-4776649232>

Relay note: a CodeRabbit rate-limit / no-review warning means incomplete review coverage, not a clean reviewer result.

### cubic

Good findings:

- `Dive-And-Dev/chrisyau.me#137`: `ARG_MAX` risk — <https://github.com/Dive-And-Dev/chrisyau.me/pull/137#discussion_r3362579303>
- `Dive-And-Dev/chrisyau.me#144`: `modifiedDate` off-by-one — <https://github.com/Dive-And-Dev/chrisyau.me/pull/144#discussion_r3369833585>

Relay note: cubic is useful as structured advisory signal. Summary-only / no-issues output is not by itself a clean ack for merge; only live high-confidence P1/P2 findings should block.

### Codex

Good findings:

- `Dive-And-Dev/chrisyau.me#136`: duplicate bypass / multi-commit push — <https://github.com/Dive-And-Dev/chrisyau.me/pull/136#discussion_r3358146405>
- `Dive-And-Dev/diveanddev.com#30`: audit all commits — <https://github.com/Dive-And-Dev/diveanddev.com/pull/30#discussion_r3357657888>

Caveat:

- `chris-yyau/busdriver#241`: manual override / addressed-by-design — <https://github.com/chris-yyau/busdriver/pull/241#discussion_r3457897254>

Relay note: Codex has the strongest deep-blocker value, but the relay must not resurrect resolved, addressed-by-design, factually incorrect, or stale findings.

### Cursor

Good findings:

- `Dive-And-Dev/chrisyau.me#137`: `jq` fallback misses audit — <https://github.com/Dive-And-Dev/chrisyau.me/pull/137#discussion_r3362650259>
- `Dive-And-Dev/diveanddev.com#30`: `pinact` direct commits false positive — <https://github.com/Dive-And-Dev/diveanddev.com/pull/30#discussion_r3357033372>

Relay note: Cursor has lower volume, but a specific live unresolved bug finding can still block.

### Devin

Good finding / caveat:

- `Dive-And-Dev/jikdak#219`: MPFA audience tag omission — <https://github.com/Dive-And-Dev/jikdak/pull/219#discussion_r3453861474>
- `chris-yyau/busdriver#241`: self-correction / factually incorrect — <https://github.com/chris-yyau/busdriver/pull/241#discussion_r3457903805>

Relay note: Devin `SUCCESS` status means the reviewer completed, not that the PR is clean. Treat only live unresolved inline `BUG` / `🚩` findings as blockers.

## Policy conclusion for relay PR-grind

- The source of truth for blockers is **live unresolved non-outdated review threads** plus current-head actionable review bodies/comments.
- Check/status completion only means the reviewer completed a run. It is not a clean ack.
- CodeRabbit rate-limit / no-review output means incomplete review coverage, not clean.
- cubic no-issues / summary-only output is advisory and not a clean ack by itself.
- Devin `SUCCESS` is not a clean ack; only live unresolved inline `BUG` / `🚩` findings should block.
- Stale, outdated, resolved, addressed-by-design, and factually incorrect threads must not block once that state is established from GitHub thread/review semantics or explicit reviewer self-correction.
- When state is unclear, fail closed as `wait` or `blocked`; do not infer clean from silence.
