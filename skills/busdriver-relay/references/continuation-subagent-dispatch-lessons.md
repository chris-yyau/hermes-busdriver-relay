# Continuation + Subagent Dispatch Lessons

Use when the user says variants of “繼續”, “繼續 subagent 完成 relay”, “完成整個 relay”, or complains that Hermes is not delegating enough.

## Durable workflow lesson

- Treat the message as an instruction to **continue the relay pipeline**, not as a request for a status-only summary.
- First do a small Phase-0 read-only status refresh: repo branch/dirty state, current HEAD, open PRs, and current relay docs/status.
- If the previous slice is merged/clean and no explicit next task is supplied, choose the next smallest safe relay slice from live docs/status rather than asking the user to pick.
- Dispatch a mutating subagent for the implementation slice immediately, with strict scope, TDD, verifier commands, and explicit bans on commit/push/PR/merge/marker writes.
- Keep main Hermes as operator/verifier/finalizer: after subagent completion, read back files/diff, run focused/full tests + smoke/static scan, then perform Delivery Mode finalization only through litmus/pre-PR and latest-head PR-grind semantics.

## Slice-selection pattern observed

When `hermes-busdriver-litmus-status` exists but Delivery Mode still only says litmus/pre-PR semantics must be verified procedurally, the next safe slice is to integrate that read-only helper as evidence in `hermes-busdriver-delivery-status` and, if minimal, `hermes-busdriver-finalization-readiness` handoff envelopes. The integration must remain read-only and keep all authority flags false.

## Pitfalls

- Do not answer only with “I will continue” or a plan. Dispatch the subagent in the same turn.
- Do not wait for a perfect roadmap. If the repo is clean and docs identify deferred finalization evidence work, choose a narrow evidence/status slice.
- Do not let the subagent own finalization. It returns a dirty tree; main Hermes verifies and finalizes under gates.
- Do not infer that a read-only helper grants commit/PR/merge authority. It is evidence only.
