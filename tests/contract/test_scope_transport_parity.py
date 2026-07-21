"""v16-r31 C6: the scope transport, tested across both languages that read it.

The wrapper joined the declared scope with "\\n" and the adapter split it on /\\r?\\n/. That is not
a transport, it is an ambiguity: a newline-joined list has no way to say "this pattern contains a
newline". So a single declared scope of `safe\\n**` did not arrive as one pattern the adapter would
refuse — it arrived as TWO, `safe` and `**`, and the second is a repo-wide allow nobody declared,
assembled out of the very character the wrapper's own scope_token_rejected() exists to reject.
Every rejection downstream was undone by the framing upstream of it.

These tests run the REAL adapter source under node's type stripping rather than grepping it: the
extraction below is the shipped file's own text, so a change to the shipped matcher fails here.
Both directions are asserted, because both are load-bearing — the wrapper must never emit a pattern
the adapter must reject, and the adapter must never read a pattern the wrapper did not emit.
"""
import json
import runpy
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PI_TOOLS = ROOT / "adapters" / "pi" / "busdriver-tools.ts"
PI_WRAPPER = ROOT / "scripts" / "pi" / "run-pi-busdriver-draft"
NODE = Path("/Users/vfrvndtt/.hermes/node/bin/node")

NEWLINE_PATTERN = "safe\n**"


@pytest.fixture(scope="module")
def wrapper() -> dict:
    return runpy.run_path(str(PI_WRAPPER))


@pytest.fixture(scope="module")
def adapter(tmp_path_factory) -> Path:
    """The real adapter source, minus the pi-runtime imports, loadable by node.

    Nothing is copied or restated: everything above `export default function` is the source's own
    text. The imports are dropped because they need the Pi package installed; none of the functions
    under test call into them.
    """
    body = PI_TOOLS.read_text().split("export default function")[0]
    body = "\n".join(line for line in body.splitlines() if not line.startswith("import "))
    body = 'import { relative, resolve } from "node:path";\n' + body
    module = tmp_path_factory.mktemp("adapter-scope") / "scope.ts"
    module.write_text(
        body
        + "\nexport { parseScopeList, scopeTokenRejected, scopeMatches, normalizeRel, runRel };\n"
    )
    return module


def node_eval(module: Path, expression: str) -> dict:
    """Evaluate `expression` against the adapter, returning {ok, value} or {ok: false, error}."""
    script = (
        f"import {{ parseScopeList, scopeTokenRejected, scopeMatches, normalizeRel, runRel }} from {json.dumps(str(module))};\n"
        "let out;\n"
        f"try {{ out = {{ ok: true, value: {expression} }}; }}\n"
        "catch (e) { out = { ok: false, error: e.message }; }\n"
        "console.log(JSON.stringify(out));\n"
    )
    cp = subprocess.run(
        [str(NODE), "--experimental-strip-types", "--input-type=module", "-e", script],
        capture_output=True, text=True, check=False,
    )
    assert cp.returncode == 0, f"node failed: {cp.stderr}"
    return json.loads(cp.stdout)


def test_the_extracted_adapter_really_runs(adapter):
    """Guard against a vacuous suite: a broken extraction would make every test below pass emptily."""
    assert node_eval(adapter, 'parseScopeList(JSON.stringify(["src/*.py"]))') == {"ok": True, "value": ["src/*.py"]}


@pytest.mark.parametrize("name", ["..foo", "...", "..events.jsonl"])
def test_adapter_relative_containment_accepts_dotdot_prefixed_leaf_names(adapter, name: str):
    """Only a parent path component escapes; a leaf whose ordinary name starts with `..` does not."""
    assert node_eval(adapter, f"normalizeRel({json.dumps('/repo/' + name)}, '/repo')") == {
        "ok": True,
        "value": name,
    }
    expression = (
        "(() => { process.env.BD_BROKER_ROOT_RUN = '/repo'; "
        f"return runRel({json.dumps('/repo/' + name)}); }})()"
    )
    assert node_eval(adapter, expression) == {"ok": True, "value": name}


def test_adapter_relative_containment_still_rejects_a_real_parent_escape(adapter):
    assert node_eval(adapter, "normalizeRel('/outside', '/repo')") == {
        "ok": False,
        "error": "path_escape",
    }
    expression = (
        "(() => { process.env.BD_BROKER_ROOT_RUN = '/repo'; return runRel('/outside'); })()"
    )
    assert node_eval(adapter, expression) == {"ok": False, "error": "run_root_escape"}


def test_the_wrapper_refuses_to_emit_a_newline_pattern(wrapper):
    """Half one: the encoder must never be able to state what the decoder must reject."""
    with pytest.raises(SystemExit):
        wrapper["scope_transport"]([NEWLINE_PATTERN])


def test_the_adapter_refuses_a_newline_pattern_it_can_now_see(adapter):
    """Half two: JSON keeps the newline INSIDE the element, so scopeTokenRejected() finally sees it.

    Under the old transport this pattern never reached a rejection at all — it had already been
    split into two innocuous-looking ones before anything examined it.
    """
    assert node_eval(adapter, f"parseScopeList(JSON.stringify([{json.dumps(NEWLINE_PATTERN)}]))") == {
        "ok": False, "error": "scope_pattern_rejected",
    }


def test_a_newline_pattern_never_becomes_two_patterns(adapter):
    """The exploit itself: one declared pattern must never turn into a repo-wide `**`."""
    result = node_eval(adapter, f"parseScopeList(JSON.stringify([{json.dumps(NEWLINE_PATTERN)}]))")

    assert result["ok"] is False
    assert result.get("value") != ["safe", "**"], "the scope split into two patterns"


def test_the_old_newline_joined_transport_is_refused_not_split(adapter):
    """A stale wrapper handing this adapter a newline-joined list must fail closed rather than
    fall back to the splitting it used to do."""
    assert node_eval(adapter, f"parseScopeList({json.dumps(NEWLINE_PATTERN)})") == {
        "ok": False, "error": "scope_transport_invalid",
    }


@pytest.mark.parametrize("hostile", [
    "safe\n**",
    "safe\r\n**",
    "safe\r**",
    "safe **",
    "safe**",
    "a\\b.py",
    "a\x00b",
    "\x1b[0m**",
    "tab\there",
])
def test_both_sides_reject_the_same_forbidden_characters(hostile: str, adapter, wrapper):
    assert wrapper["scope_token_rejected"](hostile) is True, f"the wrapper accepted {hostile!r}"
    assert node_eval(adapter, f"scopeTokenRejected({json.dumps(hostile)})") == {
        "ok": True, "value": True,
    }, f"the adapter accepted {hostile!r}"


@pytest.mark.parametrize("scope", [
    ["src/*.py"],
    ["src/**", "docs/*.md"],
    [],
    ["a b/c.txt"],
    ["**"],
    ["src/app.py", "src/other.py"],
])
def test_the_wrapper_encodes_exactly_what_the_adapter_decodes(scope: list, adapter, wrapper):
    """Parity IS the contract: whatever the wrapper emits, the adapter reads back identically."""
    encoded = wrapper["scope_transport"](scope)

    assert node_eval(adapter, f"parseScopeList({json.dumps(encoded)})") == {"ok": True, "value": scope}


@pytest.mark.parametrize("value", ['{"not": "an array"}', '"a string"', "[1, 2]", '["ok", 7]', "[[]]", "not json"])
def test_the_adapter_defaults_deny_on_any_scope_it_cannot_read(value: str, adapter):
    """An unparseable scope is not an empty scope, it is an unknown one — and unknown denies."""
    assert node_eval(adapter, f"parseScopeList({json.dumps(value)})")["ok"] is False


def test_an_unset_scope_reads_as_empty_and_pathAllowed_denies_on_empty(adapter):
    """Unset is the one non-error case, and it still denies: pathAllowed() requires a non-empty
    allowlist, so "no scope declared" has always meant "nothing may be written"."""
    assert node_eval(adapter, "parseScopeList(undefined)") == {"ok": True, "value": []}
    assert node_eval(adapter, 'parseScopeList("")') == {"ok": True, "value": []}


@pytest.mark.parametrize("path,pattern,expected", [
    ("src/app.py", "src/*.py", True),
    ("src/deep/app.py", "src/*.py", False),
    ("src/deep/app.py", "src/**", True),
    ("docs/a/b/readme.md", "**/*.md", True),
    ("src/app.py\n", "src/*.py", False),
    ("src/app.py", "src/app.py", True),
    ("evil.py", "*.py", True),
    ("a/b.py", "*.py", False),
    ("anything/at/all.txt", "**", True),
])
def test_both_matchers_agree_on_the_same_pattern(path: str, pattern: str, expected: bool, adapter, wrapper):
    """One declared scope, two implementations. A disagreement is a hole in the permissive one."""
    assert wrapper["scope_matches"](path, pattern) is expected

    assert node_eval(adapter, f"scopeMatches({json.dumps(path)}, {json.dumps(pattern)})") == {
        "ok": True, "value": expected,
    }
