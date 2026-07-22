# Polyglot production-dispatch closure and exact provenance

Use this when a Busdriver gate statically proves that production code cannot launch ambient or unauthenticated executables across shell, Python, and JavaScript/TypeScript.

## 1. Inventory closure comes before syntax scanning

Do not discover dispatch consumers with a narrow textual regex and then assume the resulting set is complete. A new alias or computed import can evade both discovery and the scanner.

- Start from the complete installed/production source inventory or an AST-based consumer inventory.
- Authenticate that inventory against the manifest/boundary before scanning.
- Treat a newly introduced executable source outside the inventory as a closure failure even when its individual calls look safe.
- Keep discovery tests independent from direct-call diagnostics so a scanner blind spot cannot make the discovery test vacuous.

## 2. Python dispatch requires alias and expression closure

Model process APIs by module and callable identity, not only by attribute spelling. Cover:

- direct modules and import aliases (`import subprocess as sp`);
- imported callables (`from subprocess import Popen as launch`);
- module aliases and function-object alias chains;
- constant computed modules (`__import__("subprocess")`, `importlib.import_module("subprocess")`);
- constant computed members (`getattr(sp, "run")`, `sp.__dict__["run"]`);
- subprocess, os exec/spawn/system, and asyncio subprocess families;
- `shell=True`, `executable=...`, and equivalent override arguments.

If a recognized dispatch expression has an unresolved module, API, executable head, shell flag, override, spread, or computed member, emit an explicit `ambiguous_dispatch`-style failure. Do not silently omit the call. Add controls for unrelated objects so fail-closed logic does not become a broad name-based false positive.

## 3. JavaScript/TypeScript aliases must include optional and computed forms

Prefer a real parser when available. If a conservative scanner is used, cover the complete call/alias grammar rather than only `cp.spawn(...)`:

- CommonJS/ESM imports, destructuring aliases, member aliases, and alias chains;
- direct, optional (`cp?.spawn`), computed (`cp["spawn"]`), and optional-computed (`cp?.["spawn"]`) members;
- computed property identifiers whose literal values are locally resolvable;
- unresolved/dynamic property names and unsupported first-argument expressions;
- direct and sync variants of spawn, exec, and execFile.

A known child-process object plus an unsupported/dynamic call shape must fail closed. An unrelated `fake.spawn` or `fake[method]` must remain a negative control.

## 4. Parameterized launcher exemptions must be exact

Path name plus function name is not provenance. Neither is an existential search for a trusted assignment somewhere in the function.

For a launcher that intentionally receives an unresolved argv parameter:

1. Bind the exemption to the exact installed path, function, parameter, and call expression.
2. Audit every call site at every nesting depth; do not inspect only module-scope calls.
3. Resolve trusted helper expressions and reject bare/relative literal heads.
4. Bind statement order and control flow. A validation assignment after `Popen`, or inside an unreachable branch, must not authorize an earlier dispatch.
5. For a small stable launcher, a maintained SHA-256 over `ast.dump(function, include_attributes=False)` is an acceptable exact structural contract. Keep the expected fingerprint explicit and add a mutation test that reorders validation and dispatch.

When the launcher changes legitimately, update the fingerprint only after reviewing the full new AST and rerunning closure tests.

## 5. Keep dormant executors out of production bytes

A runtime blocker does not make a dangerous executor harmless if the shell/process implementation still ships in production. If tests need to exercise a relaxed legacy path:

- remove the executor from production code;
- inject it only from an explicitly non-installed test fixture;
- preserve the original call contract exactly, including normalization such as `None -> []`;
- test that the fixture cannot enter the production manifest/source inventory.

After moving behavior into a fixture, run both the direct gate tests and every higher-level suite that invokes the fixture indirectly; otherwise cascading JSON/shape failures can masquerade as unrelated agent failures.

## 6. Regression and suite discipline

For each bypass, keep the exact RED payload and a nearby negative control. Operator-reproduce the payload independently after the mutator reports GREEN.

After any source-byte change, including test fixtures:

- rerun every full-suite partition, not only the partition believed to own the file;
- compare partition `expected` node counts, not only the number reported as passed (skips still count toward inventory);
- re-collect whenever test functions change;
- refresh embedded pins before the final full suite if production bytes changed, then prove a second fixed-point pass changes nothing;
- run hygiene against the correct path semantics (for example, plugin-relative manifest paths are not relay-repo-relative paths).

Targeted tests are evidence for the local repair, never a substitute for full-suite closure.

## 7. Immutable review-lane preflight

Before START:

- write the checksum sidecar in the verifier's canonical format, usually `<sha256>  <basename>\n`, not an absolute pathname;
- authenticate and immutable-pin both boundary and sidecar;
- verify candidate/view builders against the same expected tree and source digest.

A failed START may leave empty lane/temp directories even when it writes no artifacts. Inspect them first and remove only directories proven empty before retrying. Never reuse a partially populated lane. Once START succeeds, preserve that candidate/view; any source repair creates a new round.
