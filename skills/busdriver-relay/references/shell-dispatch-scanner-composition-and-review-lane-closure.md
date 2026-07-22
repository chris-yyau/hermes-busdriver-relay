# Shell-dispatch scanner composition and immutable review-lane closure
> **HISTORICAL / SUPERSEDED — NON-PRODUCTION.** Current policy authority: repository-root `docs/coding-workflow-authority-map.md`; any later current-tense or positive-authority wording is retained evidence only and MUST NOT be treated as executable/current policy.

Use this when a delivery gate statically inventories executable dispatch in production shell, especially after a reviewer finds a parser bypass.

## 1. Treat the scanner as a security parser

A scanner that passes isolated feature tests can still fail on compositions. Test the Cartesian seams, not just each feature independently:

- forwarding builtins: `command`, `builtin`, `exec`;
- forwarder options and option arguments: `--`, `exec -a NAME`, known and unknown options;
- assignments before commands and assignment-looking forwarder arguments;
- redirections before and after forwarder options;
- adjacent numeric IO numbers versus whitespace-separated numeric command words;
- `$()` and process substitutions;
- legacy backtick substitutions, including escaped nested backticks;
- arithmetic expansion containing command or legacy substitutions;
- wrappers, functions, conditionals, groups, pipelines, separators and EOF states.

Every ambiguous or unclosed state must fail closed with an auditable diagnostic rather than silently discarding the possible command head.

## 2. Parser invariants that prevent recurring bypasses

### Numeric IO-number adjacency

Preserve lexical adjacency. In `2>/dev/null`, `2` is an IO-number prefix; in `2 >/dev/null`, `2` is a command word. Emit a distinct token only for an adjacent numeric prefix immediately followed by a real redirection operator. Add both positive and whitespace-separated control cases.

### Forwarder-state precedence

When a forwarder is active, consume its option argument and then its forwarded executable head before generic assignment handling. Otherwise `exec -a A=B curl ...` can treat `A=B` as an assignment, consume `curl` as the option argument, and lose the true head. Assignment-looking forwarded heads should be reported conservatively, not skipped.

### Arithmetic versus command substitution

Distinguish `$((...))` from `$(...)` before dispatching to a nested parser, including inside double quotes. Parse arithmetic expansion with balanced delimiters, quotes and escapes. Do not scan pure arithmetic identifiers as shell commands, but recursively scan executable `$()` or backtick substitutions nested inside arithmetic.

### Legacy backticks

Parse backticks outside single quotes and inside double quotes. Preserve line provenance, reject unterminated forms, and recursively scan the extracted body. Escaped backticks inside an outer backtick substitution can delimit a nested legacy substitution after one shell layer is removed; normalize one escape layer at a time while preserving the remaining backslashes. Test multiple nesting levels and unbalanced forms.

## 3. Non-vacuous regression pattern

For each bypass:

1. Reproduce RED against the immutable previous candidate.
2. Inject the exact shell fragment into a real production shell source.
3. Assert the production violation path reports the true executable head, not merely a later URL/argument or a generic diagnostic.
4. Add a nearby negative control that proves the lexer did not over-classify syntax.
5. Re-run the complete scanner contract file.
6. Re-collect the full suite inventory. A newly added test function changes partition counts even when file membership is unchanged.
7. Run the exact full suite, fixed-point and hygiene on the bytes that will be frozen.

Useful examples:

```sh
command 2>/dev/null curl https://example.invalid/
exec -a A=B curl https://example.invalid/
x=`curl`
echo $(( $(curl https://example.invalid/) ))
x=`echo \`curl\``
```

Controls should include pure arithmetic, ordinary quoted diagnostics, and whitespace-separated `2 >file` behavior.

## 4. Pin-refresh tools are partially mutating transactions

A refresh helper may rewrite the manifest or several embedded assignments before failing on a stale mapping. Never infer “no mutation” from a non-zero exit.

Before running it:

- seal or hash the full source inventory;
- validate that every configured assignment name and executable-key set matches the current source schema;
- keep runtime/cache outside the repo.

After any failure:

- compare the entire source inventory to the pre-run digest;
- inspect every changed assignment for dropped keys/comments or stale schema;
- restore exact bytes or complete the refresh to a proven fixed point;
- reuse prior suite evidence only if the final source digest is byte-for-byte identical to the suite-tested digest; otherwise rerun the suite.

A successful fixed-point check must report no changed scripts and no manifest change on a subsequent pass.

## 5. Immutable reviewer-lane acceptance

A reviewer process ending is not review closure. A lane is acceptable only when all of these are true:

- START source/candidate/view closures are valid;
- the reviewer inspected the same immutable review-view digest;
- the report is non-empty and ends with the required verdict line;
- END source/candidate/view closures are valid and match START;
- High/Medium findings are repaired or closed with durable evidence.

Authentication, quota, timeout or transport failures produce a failed attempt, not CLEAN. Preserve the raw attempt and retry or switch transport/model only against the same immutable view. Do not overwrite a frozen report; use a distinct failed-attempt artifact and a fresh report path. If a repair changes source bytes, close the old round as blocked and create a new boundary, candidate and three-party review round.
