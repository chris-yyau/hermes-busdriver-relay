FULL_RELAY_ROLE_MAP = {
    "relay.impl.primary": "pi",
    "relay.impl.secondary": "opencode",
    "relay.impl.fallback": "opencode",
    "relay.review.fast": "grok",
    "relay.review.long_context": "gemini",
    "relay.ide.manual": "zed",
    "relay.expert_witness.ultraoracle": "ultraoracle",
    "relay.litmus.reviewer": "codex",
    "relay.blueprint.reviewer_1": "agy",
    "relay.blueprint.reviewer_2": "claude-code",
    "relay.blueprint.reviewer_3": "grok",
    "relay.blueprint.arbiter": "codex",
    "relay.pr.lead": "codex",
    "relay.pr.backstop": "claude-code",
    "relay.council.architect": "inline",
    "relay.council.pragmatist": "agy",
    "relay.council.critic": "codex",
    "relay.council.researcher": "grok",
    "relay.council.skeptic": "claude-code",
}

NON_PROGRAMMATIC_RELAY_ROLES = {
    "relay.impl.primary",
    "relay.impl.secondary",
    "relay.impl.fallback",
    "relay.ide.manual",
}

UNVERIFIED_ADAPTER_RELAY_ROLES = {
    "relay.impl.primary",
    "relay.impl.secondary",
    "relay.impl.fallback",
}

REVIEW_SENSITIVE_RELAY_ROLES = {
    role
    for role in FULL_RELAY_ROLE_MAP
    if not role.startswith("relay.impl.") and role != "relay.ide.manual"
}
