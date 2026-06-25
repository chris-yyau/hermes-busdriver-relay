# ADR 0001 — Repository Boundary

## Context

Hermes needs to understand the user's Busdriver workflow without becoming a second Busdriver. Busdriver remains the canonical coding pipeline, gate runtime, MCP/plugin router, and reviewer/worker dispatcher.

## Decision

This repository stores only Hermes-side relay artifacts:

- Hermes skill source;
- read-only status scripts;
- contract tests;
- integration docs/ADRs.

It must not vendor Busdriver, Claude Code plugin state, MCP configuration, runtime markers, credentials, browser cookies, or generated review artifacts.

## Consequences

- Hermes reads Busdriver source-of-truth JIT at runtime.
- Drift is detected by status/tests instead of solved by copying Busdriver internals.
- Repo-changing launchers remain disabled until hook-runtime equivalence and H1-H13 checks pass.

## Revisit trigger

Revisit only if Busdriver defines an explicit Hermes integration surface or install target.
