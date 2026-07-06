# Balanced Agent Work Planning Lessons

Session lesson from adding a read-only balanced-agent planning surface to `hermes-busdriver-relay`.

## Pattern

When the user asks for Hermes to “balance” or “parallelize” agent work in the relay, start with a **read-only planning envelope**, not real concurrent repo mutation.

Safe first shape:

- one gated mutating draft lane (`max_parallel=1`, `parallelizable=false`, `requires_gate=true`, Pi-default under current policy);
- multiple read-only lanes for review/status/scanning (`max_parallel>1`, `parallelizable=true`);
- main Hermes remains operator/verifier/finalizer;
- commit/push/PR/merge/marker-write remain Delivery Mode only;
- the helper must not launch agents, call Pi/Codex/GitHub, mutate repos, or write markers; when Pi is the default draft lane, its planning metadata should name Pi while keeping all execution flags false.

## Schema / authority pitfalls

- Do not put non-false values under keys ending in `*_allowed` unless they are truly authority grants and intentionally safe. Recursive authority scanners treat `*_allowed` as authority-like.
- A positive policy fact such as read-only lanes being parallelizable should be named something like `read_only_lanes_parallelizable`, not `readonly_parallel_allowed`.
- For a mutating draft lane, keep `repo_mutation_allowed: false`; put explanatory text in a non-authority key such as `draft_mutation_scope`.
- Capability inventory entries should remain exactly metadata-only (`path`, `available`). Do not add command args, selected agents, execution results, or authority fields to inventory entries.

## Tests to require

- helper emits deterministic JSON with schema/read_only/ok/policy/lane/execution sections;
- recursive authority-safety test fails if any `*_allowed` or execution side-effect flag is non-false;
- draft lane is single-flight and gated;
- read-only lanes are parallelizable and non-mutating;
- no-dispatch execution flags stay false (`external_agents_called`, `subprocess_dispatch_called`, `pi_called`, `codex_called`, `github_called`, `marker_writes_performed`, `repo_mutations_performed`);
- delivery-status capability inventory includes the helper and other public helpers as metadata-only entries.

## Implementation language rationale

For relay helper/envelope surfaces, Python remains a good bootstrap/default choice because the relay is currently a Hermes-owned probe/contract-test layer: stdlib JSON/path/subprocess handling, `pytest` contract tests, `py_compile`, and smoke integration keep slices small and fail-closed without adding a second build ecosystem. Revisit Go/Rust/Node only for a future long-running scheduler/daemon/queue, not for static read-only evidence helpers.