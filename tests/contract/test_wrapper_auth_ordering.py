"""v16-r28 item 3: the wrappers authenticate their worker BEFORE they can ever dispatch it.

Production dispatch is fixed `policy_blocked`, so no runtime test can observe this ordering — the
blocker returns long before the worker is launched. That is exactly the risk: the ordering is a
property nothing currently exercises, and the day the blocker is lifted is the day it matters. A
reordering that moved credential setup above the digest check would break no test today and hand
an unauthenticated binary the operator's live credentials tomorrow.

So it is asserted STRUCTURALLY, against the source: within each wrapper's `main()`, the call that
authenticates the worker executable must appear before the call that copies credentials into the
private HOME, and both before the call that launches it. This is a source-order check, which is a
weaker claim than a behavioural one — it cannot see a reorder hidden behind a helper — but it is
the strongest claim available while dispatch is blocked, and it fails loudly on the edit that
would otherwise pass silently.
"""
import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]

# (wrapper, authenticates-the-worker, copies-credentials, launches-the-worker)
WRAPPERS = {
    "pi": (
        "scripts/pi/run-pi-busdriver-draft",
        ("trusted_pi_executable", "trusted_node_executable"),
        ("copy_private_pi_config",),
        ("run",),
    ),
    "opencode": (
        "scripts/opencode/run-opencode-busdriver-draft",
        ("trusted_opencode_executable",),
        # opencode_child_env() is where prepare_private_opencode_home() copies live credentials
        # into the HOME this process is about to hand the worker.
        ("opencode_child_env",),
        ("run",),
    ),
}


def main_function(relative: str) -> ast.FunctionDef:
    tree = ast.parse((ROOT / relative).read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError(f"{relative} has no main()")


def first_call_index(fn: ast.FunctionDef, names: tuple[str, ...]) -> int:
    """Source order of the first call to any of `names`, by line number."""
    hits = [
        node.lineno
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in names
    ]
    assert hits, f"main() never calls any of {names} — the anchor moved, so this test is blind"
    return min(hits)


@pytest.mark.parametrize("name", sorted(WRAPPERS))
def test_worker_is_authenticated_before_credentials_are_copied(name: str):
    """The digest check must precede handing the worker a HOME with live credentials in it."""
    relative, auth, credentials, _dispatch = WRAPPERS[name]
    fn = main_function(relative)

    assert first_call_index(fn, auth) < first_call_index(fn, credentials), (
        f"{relative}: credentials are prepared before the worker executable is authenticated"
    )


@pytest.mark.parametrize("name", sorted(WRAPPERS))
def test_worker_is_authenticated_before_it_is_launched(name: str):
    """The property that must survive the blocker being lifted."""
    relative, auth, _credentials, dispatch = WRAPPERS[name]
    fn = main_function(relative)

    assert first_call_index(fn, auth) < first_call_index(fn, dispatch), (
        f"{relative}: the worker is launched before it is authenticated"
    )


@pytest.mark.parametrize("name", sorted(WRAPPERS))
def test_policy_blocker_precedes_every_one_of_them(name: str):
    """Today's guarantee: nothing above happens at all, because the blocker returns first."""
    relative, auth, credentials, dispatch = WRAPPERS[name]
    fn = main_function(relative)
    blocker = first_call_index(fn, ("production_dispatch_blocker",))

    assert blocker < first_call_index(fn, auth)
    assert blocker < first_call_index(fn, credentials)
    assert blocker < first_call_index(fn, dispatch)
