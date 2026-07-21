"""v16-r32 item 7: the child must not choose how much memory this process spends.

`capture_output=True` and `.communicate()` read until EOF. The bound that follows them —
`if len(cp.stdout) > MAX_HELPER_STDOUT_BYTES`, `tail(stdout, 4000)` — is a bound on what gets
PARSED or PERSISTED, and both of those run after the bytes are already resident. agent-draft's own
comment says "bounded BEFORE json.loads sees it", which is true and beside the point: the worker
that produced them is untrusted, and it chose the number.

So the bound moves to the pipe, where the number is ours. Over it, output is REFUSED rather than
sliced — the same reasoning `REDACTED_OVERSIZED` already encodes: the value classes for `token:`
and `Bearer` are unbounded, so a slice can cut away the very prefix that identifies a secret and
emit the remainder as ordinary text. An unmatched fragment of a secret is still a secret.

Draining both pipes to EOF is not optional, which is the part that makes this subtle: a child
blocked writing into a pipe nobody reads never exits, so "stop reading at the bound" and "deadlock"
are the same instruction. The bound is therefore on what is KEPT, not on what is read.
"""
import ast
import inspect
import json
import os
import re
import runpy
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def production_sources() -> list[Path]:
    """Every production Python file, found rather than listed.

    These are extension-less executables, so "is it Python" is answered by parsing it, not by a
    suffix. A hand-kept list is exactly the thing that goes stale — this suite previously named
    seven modules while fifteen defined the primitive, and the eight it omitted were the eight
    nobody checked.
    """
    found = []
    for base in ("scripts", "adapters"):
        for path in sorted((ROOT / base).rglob("*")):
            if not path.is_file() or path.suffix in {".sh", ".md", ".json", ".ts", ".lock"}:
                continue
            try:
                ast.parse(path.read_text(errors="replace"))
            except (SyntaxError, ValueError):
                continue
            found.append(path)
    return found


def modules_defining(symbol: str) -> list[str]:
    pattern = re.compile(rf"^def {re.escape(symbol)}\(", re.M)
    return sorted(
        str(path.relative_to(ROOT))
        for path in production_sources()
        if pattern.search(path.read_text(errors="replace"))
    )


# Derived, never typed: every module that restates the primitive is a module that must obey it.
BOUNDED_CAPTURE_MODULES = modules_defining("run_bounded")


def load(module_path: str) -> dict:
    return runpy.run_path(str(ROOT / module_path))


def test_the_enumeration_finds_every_copy_of_the_primitive():
    """The guard on the guard: a derivation that silently finds nothing would pass every test below.

    The floor is the count at the time this was written. It is a floor and not an equality because
    a new bounded runner is a fine thing to add — being SKIPPED by this file is not.
    """
    assert len(BOUNDED_CAPTURE_MODULES) >= 15, BOUNDED_CAPTURE_MODULES
    assert "scripts/hermes-busdriver-deliver" in BOUNDED_CAPTURE_MODULES


def test_no_production_module_uses_an_unbounded_capture_api():
    """The enumeration. `capture_output=True` and `.communicate()` have no bound, by construction.

    A grep rather than a behavioural test, and deliberately: the point is that the NEXT helper
    someone adds cannot reintroduce the shape, and no per-site test covers a site nobody has
    written yet. `run_bounded()` is the one sanctioned spelling.
    """
    offenders = []
    candidates = sorted((ROOT / "scripts").rglob("*")) + sorted((ROOT / "adapters").rglob("*.py"))
    for path in candidates:
        if not path.is_file() or path.suffix in {".sh", ".md", ".json", ".ts"}:
            continue
        text = path.read_text(errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            # Prose, not code: the primitive's own docstring names the API it replaces, and a
            # backtick is how this codebase quotes an identifier it is talking ABOUT.
            if stripped.startswith("#") or "`" in stripped:
                continue
            where = f"{path.relative_to(ROOT)}:{number}"
            if "capture_output=True" in stripped and "def _bounded_run(" not in stripped:
                offenders.append(f"{where}: capture_output=True reads until EOF")
            if ".communicate(" in stripped:
                offenders.append(f"{where}: .communicate() reads until EOF")
            if "check_output(" in stripped:
                offenders.append(f"{where}: check_output() reads until EOF")

    assert offenders == [], (
        "unbounded subprocess capture (use the module's run_bounded()):\n" + "\n".join(offenders)
    )


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_every_capturing_module_defines_the_bounded_primitive(module_path: str):
    ns = load(module_path)
    assert callable(ns.get("run_bounded")), f"{module_path} has no run_bounded()"
    assert isinstance(ns.get("MAX_CAPTURED_BYTES"), int), f"{module_path} has no MAX_CAPTURED_BYTES"
    # Small enough to be a real bound, big enough that the 4000-char tail it feeds is never starved.
    assert 8192 <= ns["MAX_CAPTURED_BYTES"] <= 1 << 20


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_the_bound_is_identical_across_every_copy(module_path: str):
    """Restated, not shared — so a contract test is the only thing keeping them equal."""
    canonical = load(BOUNDED_CAPTURE_MODULES[0])["MAX_CAPTURED_BYTES"]
    assert load(module_path)["MAX_CAPTURED_BYTES"] == canonical


# --- the primitive's own behaviour, proved against real children ---


AGENT_DRAFT = "scripts/hermes-busdriver-agent-draft"


def python_says(script: str) -> list:
    return [sys.executable, "-I", "-c", script]


def test_a_high_volume_child_on_both_streams_neither_deadlocks_nor_is_retained():
    """The deadlock case and the memory case are the same test, because they are the same bug.

    A child writing megabytes to BOTH pipes deadlocks any drainer that reads one to EOF first —
    the classic reason `.communicate()` exists. It must also not cost this process the megabytes.
    """
    ns = load(AGENT_DRAFT)
    limit = ns["MAX_CAPTURED_BYTES"]
    child = python_says(
        "import sys\n"
        f"sys.stdout.write('O' * {limit * 4})\n"
        f"sys.stderr.write('E' * {limit * 4})\n"
    )

    result = ns["run_bounded"](child, timeout=60)

    assert result.overflowed is True
    assert result.stdout == "" and result.stderr == "", "overflowing output must be discarded, not sliced"


def test_output_just_under_the_bound_survives_whole():
    """The bound must not cost the ordinary case: a normal helper's output arrives intact."""
    ns = load(AGENT_DRAFT)
    payload = "x" * (ns["MAX_CAPTURED_BYTES"] - 64)

    result = ns["run_bounded"](python_says(f"import sys; sys.stdout.write('{payload[:100]}' * {len(payload) // 100})"), timeout=60)

    assert result.overflowed is False
    assert len(result.stdout) == (len(payload) // 100) * 100
    assert result.returncode == 0


def test_a_secret_spanning_the_capture_boundary_never_reaches_the_output():
    """The reason overflow REFUSES instead of slicing.

    A slice at the bound cuts a secret in half. The half that carries `token:` identifies it and is
    redactable; the half that does not is indistinguishable from ordinary text, and it is the half
    that survives. No window size fixes it — the prefix sits arbitrarily far from the cut.
    """
    ns = load(AGENT_DRAFT)
    limit = ns["MAX_CAPTURED_BYTES"]
    secret = "ghp_" + "A" * 36
    child = python_says(
        "import sys\n"
        f"sys.stdout.write('p' * {limit - 20})\n"   # lands the secret astride the bound
        f"sys.stdout.write('token: {secret}')\n"
        f"sys.stdout.write('q' * {limit})\n"
    )

    result = ns["run_bounded"](child, timeout=60)

    assert result.overflowed is True
    assert secret not in result.stdout
    assert "A" * 36 not in result.stdout
    assert result.stdout == ""


def test_an_overflowing_child_is_killed_rather_than_left_streaming():
    """Fail-closed means the child stops, not that we politely read its whole firehose."""
    ns = load(AGENT_DRAFT)
    limit = ns["MAX_CAPTURED_BYTES"]
    child = python_says(
        "import sys\n"
        "while True:\n"
        f"    sys.stdout.write('x' * {limit})\n"
        "    sys.stdout.flush()\n"
    )

    result = ns["run_bounded"](child, timeout=30)

    assert result.overflowed is True
    assert result.returncode != 0, "an unbounded child must be killed, not waited on forever"


def test_a_timeout_still_bounds_and_reaps():
    ns = load(AGENT_DRAFT)

    result = ns["run_bounded"](python_says("import time; time.sleep(120)"), timeout=2)

    assert result.timed_out is True
    assert result.returncode != 0


def test_the_primitive_closes_every_pipe_it_opens():
    """A drain that leaks descriptors turns a long run into a different failure."""
    ns = load(AGENT_DRAFT)
    before = len(os.listdir("/dev/fd"))

    for _ in range(25):
        ns["run_bounded"](python_says("import sys; sys.stdout.write('ok'); sys.stderr.write('e')"), timeout=30)

    assert len(os.listdir("/dev/fd")) <= before + 2, "run_bounded leaked pipe descriptors"


def test_a_child_that_exits_without_reading_stdin_does_not_wedge_the_drain():
    ns = load(AGENT_DRAFT)

    result = ns["run_bounded"](python_says("import sys; sys.exit(3)"), timeout=30, stdin_bytes=b"y" * 4096)

    assert result.returncode == 3
    assert result.overflowed is False


# --- v16-r33 E: a refusal that leaves the group running has not refused anything ---


def assert_group_dies(pid: int, timeout: float = 5.0) -> None:
    """Nothing survives — waited for rather than sampled.

    A descendant is reparented to init when its leader exits, so a bounded helper can never reap it
    and must not block on it; SIGKILL is the whole of what it can promise, and SIGKILL is delivered
    asynchronously. Sampling the instant the refusal returns would race the kernel rather than test
    anything, so this asserts the same fact to a deadline instead.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    os.kill(pid, signal.SIGKILL)  # never leak a 300s sleep into the rest of the run
    raise AssertionError(f"descendant {pid} survived the overflow refusal")


def descendant_pid(marker: Path, timeout: float = 10.0) -> int:
    """The pid the child leaked, read once it is actually there rather than once we hope it is."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            text = marker.read_text().strip()
        except OSError:
            text = ""
        if text.isdigit():
            return int(text)
        time.sleep(0.02)
    raise AssertionError(f"child never recorded a descendant pid at {marker}")


# The adversary, once, reused by every module: a child that forks a descendant which INHERITS the
# pipes and outlives it. This is the shape that defeats every non-group mechanism in the file —
# the leader exits so `wait()` returns, the descendant never writes so SIGPIPE never fires, and it
# holds the write end so the drain never sees EOF.
LEAKS_DESCENDANT_THEN_OVERFLOWS = "sleep 300 &\necho $! > {marker}\nprintf '%s' {payload}\nexit 0\n"
LEAKS_DESCENDANT_THEN_HANGS = "sleep 300 &\necho $! > {marker}\nsleep 300\n"


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_run_bounded_timeout_takes_the_whole_group_in_every_module(module_path: str, tmp_path: Path):
    """Every copy of the primitive, not just the two that happened to own a Popen.

    `subprocess.run(timeout=…)` kills and reaps the DIRECT child — that is the whole of its
    contract. The descendant is reparented to init and keeps running, holding the pipe it
    inherited, which is why the deadline being honoured says nothing about the group being gone.
    """
    marker = tmp_path / "descendant.pid"
    ns = load(module_path)

    started = time.monotonic()
    result = ns["run_bounded"](
        ["/bin/sh", "-c", LEAKS_DESCENDANT_THEN_HANGS.format(marker=marker)],
        timeout=2,
    )
    elapsed = time.monotonic() - started

    assert result.timed_out is True
    assert result.returncode != 0, "a timed-out child must not be reported as a success"
    assert elapsed < 30, f"cleanup was not bounded: {elapsed:.1f}s"
    assert_group_dies(descendant_pid(marker))


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_run_bounded_overflow_takes_the_whole_group_in_every_module(module_path: str, tmp_path: Path):
    """Overflow, the path with no clock behind it.

    A timeout at least ends in a kill. Overflow ended in a `break` and a `close()` — a refusal of
    the BYTES that left the group which authored them running. The child chooses when to overflow,
    so the child chose when to survive. It exits 0 immediately, so no deadline ever expires to
    rescue this.
    """
    marker = tmp_path / "descendant.pid"
    ns = load(module_path)

    started = time.monotonic()
    result = ns["run_bounded"](
        ["/bin/sh", "-c", LEAKS_DESCENDANT_THEN_OVERFLOWS.format(marker=marker, payload="x" * 64)],
        timeout=60,
        limit=8,
    )
    elapsed = time.monotonic() - started

    assert result.overflowed is True
    assert result.stdout == "" and result.stderr == ""
    assert elapsed < 30, f"a descendant holding the pipe stalled the drain for {elapsed:.1f}s"
    assert_group_dies(descendant_pid(marker))


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_run_bounded_reaps_the_direct_child_rather_than_leaving_a_zombie(module_path: str, tmp_path: Path):
    """Killing the group is half of it; the leader is ours to reap, and only ours."""
    marker = tmp_path / "descendant.pid"
    ns = load(module_path)

    ns["run_bounded"](
        ["/bin/sh", "-c", LEAKS_DESCENDANT_THEN_HANGS.format(marker=marker)],
        timeout=2,
    )

    # Nothing of ours is left waiting to be collected. os.waitpid(-1) would reap pytest's own
    # children, so this asks the narrower question: are there any unreaped children at all?
    with pytest.raises(ChildProcessError):
        os.waitpid(-1, os.WNOHANG)


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_run_bounded_kills_descendants_that_close_their_pipes_before_leader_exit(module_path: str, tmp_path: Path):
    """A helper may not daemonize merely by closing stdout/stderr before its leader exits.

    r87 fixed descendants that kept a pipe open: the lingering drain forced a pre-reap group kill.
    A quieter descendant can redirect all descriptors to `/dev/null`, let the leader exit 0, and
    leave no live drain thread to trigger that cleanup. The process group is still child-authored
    execution and must be signalled while the unreaped leader still pins the numeric PGID.
    """
    marker = tmp_path / "quiet-descendant.pid"
    ns = load(module_path)

    result = ns["run_bounded"](
        [
            "/bin/sh",
            "-c",
            f"sleep 300 </dev/null >/dev/null 2>/dev/null &\necho $! > {marker}\nexit 0\n",
        ],
        timeout=30,
    )

    assert result.returncode == 0
    assert result.overflowed is False
    assert result.timed_out is False
    assert_group_dies(descendant_pid(marker), timeout=1.0)


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_run_bounded_baseexception_cleans_group_before_reraising(module_path: str, tmp_path: Path):
    """Operator cancellation must not orphan a mutating new-session child after Popen."""
    ns = load(module_path)
    leader_marker = tmp_path / "interrupt-leader.pid"
    child_marker = tmp_path / "interrupt-child.pid"
    script = (
        f"echo $$ > {leader_marker}\n"
        "sleep 300 </dev/null >/dev/null 2>/dev/null &\n"
        f"echo $! > {child_marker}\n"
        "sleep 300\n"
    )

    class InterruptingWatch:
        def exited(self):
            raise KeyboardInterrupt()

        def close(self):
            return None

    def fake_exit_watch(_process):
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if leader_marker.exists() and child_marker.exists():
                return InterruptingWatch()
            time.sleep(0.01)
        raise AssertionError("child did not publish pids before exit-watch interruption")

    ns["_bounded_communicate"].__globals__["_bounded_exit_watch"] = fake_exit_watch

    with pytest.raises(KeyboardInterrupt):
        ns["run_bounded"](["/bin/sh", "-c", script], timeout=30)

    assert_group_dies(descendant_pid(leader_marker), timeout=1.0)
    assert_group_dies(descendant_pid(child_marker), timeout=1.0)


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_lingering_pipe_cleanup_signals_before_the_leader_is_reaped(module_path: str, monkeypatch):
    """An exit observation must pin the PID until every possible group signal is finished.

    `Popen.poll()` is a waitpid(WNOHANG): when it reports exit it has already reaped the leader.
    A still-live pipe drainer can then send `killpg(process.pid, ...)` through a recycled numeric
    identity.  The fake deliberately makes `poll()` fatal and exposes an exit through the
    non-reaping watch instead; the group-kill canary requires `returncode is None`, and only the
    final wait is allowed to publish the return code.
    """
    ns = load(module_path)
    globals_ = ns["_bounded_communicate"].__globals__
    state = {"thread_alive": True, "signalled": False, "waited": False}

    class FakeThread:
        def join(self, timeout=None):
            return None

        def is_alive(self):
            return state["thread_alive"]

    class FakeExitWatch:
        def exited(self):
            return True

        def close(self):
            return None

    class FakeProcess:
        pid = 4242
        stdin = None
        stdout = object()
        stderr = object()
        returncode = None

        def poll(self):
            raise AssertionError("poll_reaped_leader_before_lingering_pipe_cleanup")

        def wait(self, timeout=None):
            assert state["signalled"], "the leader was reaped before the final group signal"
            state["waited"] = True
            self.returncode = 0
            return 0

    def fake_drains(_stdout, _stderr, _limit):
        return [FakeThread(), FakeThread()], bytearray(), bytearray(), [0], [0], ns["threading"].Event()

    def kill_while_identity_is_pinned(process):
        assert process.returncode is None, "a reaped leader's numeric PGID was signalled"
        state["signalled"] = True
        state["thread_alive"] = False

    monkeypatch.setitem(globals_, "_start_bounded_drains", fake_drains)
    monkeypatch.setitem(globals_, "_bounded_exit_watch", lambda _process: FakeExitWatch())
    monkeypatch.setitem(globals_, "_kill_bounded_group", kill_while_identity_is_pinned)

    result = ns["_bounded_communicate"](FakeProcess(), ["fixed-helper"], 30, None, 1024)

    assert result.returncode == 0
    assert state == {"thread_alive": False, "signalled": True, "waited": True}


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_run_bounded_does_not_signal_numeric_pgid_after_leader_reap(module_path: str, monkeypatch):
    """A BaseException after wait() must not reuse the old numeric PGID as authority.

    The main path already signalled the group before reaping.  If a later cleanup join is
    interrupted, the original exception should propagate after local bounded cleanup; it must not
    call killpg(process.pid) again after wait() has published returncode.
    """
    ns = load(module_path)
    globals_ = ns["_bounded_communicate"].__globals__
    state = {"join_calls": 0, "pre_reap_kills": 0}

    class FakeThread:
        def join(self, timeout=None):
            state["join_calls"] += 1
            if state["join_calls"] >= 3:
                raise KeyboardInterrupt("interrupt_after_reap")

        def is_alive(self):
            return False

    class FakeExitWatch:
        def exited(self):
            return True

        def close(self):
            return None

    class FakeProcess:
        pid = 4242
        stdin = None
        stdout = object()
        stderr = object()
        returncode = None

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

    def fake_drains(_stdout, _stderr, _limit):
        return [FakeThread(), FakeThread()], bytearray(), bytearray(), [0], [0], ns["threading"].Event()

    def kill_only_while_unreaped(process):
        assert process.returncode is None, "reaped leader's numeric PGID was signalled after ownership ended"
        state["pre_reap_kills"] += 1

    monkeypatch.setitem(globals_, "_start_bounded_drains", fake_drains)
    monkeypatch.setitem(globals_, "_bounded_exit_watch", lambda _process: FakeExitWatch())
    monkeypatch.setitem(globals_, "_kill_bounded_group", kill_only_while_unreaped)

    with pytest.raises(KeyboardInterrupt):
        ns["_bounded_communicate"](FakeProcess(), ["fixed-helper"], 30, None, 1024)

    assert state["pre_reap_kills"] == 1


def test_an_overflowing_child_that_leaves_a_descendant_holding_the_pipe_kills_the_whole_group(
    tmp_path: Path, monkeypatch,
):
    """The exploit: overflow the bound from a child whose descendant outlives it.

    `run_safe` killed the group on TIMEOUT only, so this path returned `stdout_capture_limit_exceeded`
    — a refusal of the bytes — while the process group that produced them kept running with the
    pipe it inherited. The worker chooses when to overflow, so the worker chose when to survive.
    """
    marker = tmp_path / "descendant.pid"
    ns = load("scripts/hermes-busdriver-deliver")
    monkeypatch.setitem(ns["run_safe"].__globals__, "MAX_CAPTURED_BYTES", 8)

    result = ns["run_safe"](
        ["/bin/sh", "-c", f"sleep 300 &\necho $! > {marker}\nprintf 'xxxxxxxxxxxxxxxxxxxxxxxx'\nexit 0\n"],
        cwd=tmp_path,
        timeout=30,
    )

    assert result["error"] == "stdout_capture_limit_exceeded"
    assert result["ok"] is False
    assert_group_dies(int(marker.read_text().strip()))


def test_a_timing_out_child_still_takes_its_whole_group_with_it(tmp_path: Path):
    marker = tmp_path / "descendant.pid"
    ns = load("scripts/hermes-busdriver-deliver")

    result = ns["run_safe"](
        ["/bin/sh", "-c", f"sleep 300 &\necho $! > {marker}\nsleep 300\n"],
        cwd=tmp_path,
        timeout=2,
    )

    assert result["error"] == "timeout"
    assert_group_dies(int(marker.read_text().strip()))


# --- the enumeration, by call site rather than by string ---

LAUNCH_APIS = {
    "subprocess.Popen",
    "subprocess.run",
    "subprocess.check_output",
    "subprocess.check_call",
    "subprocess.call",
}


def _link_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent


def _enclosing_function(node: ast.AST):
    current = getattr(node, "parent", None)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
        current = getattr(current, "parent", None)
    return None


def _keyword(call: ast.Call, name: str):
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _is_true(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_devnull(node) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "DEVNULL"


def launch_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func) in LAUNCH_APIS:
            yield node


def captures_or_bounds(call: ast.Call) -> bool:
    """The scope of the rule: a launch that keeps the child's bytes, or holds it to a clock.

    A fire-and-forget launch with no pipes and no deadline has no drain to wedge and no refusal to
    make hollow, so it is out of scope. Everything else owns a child whose descendants outlive it.
    """
    if _keyword(call, "timeout") is not None:
        return True
    if _is_true(_keyword(call, "capture_output")):
        return True
    return any(
        (value := _keyword(call, stream)) is not None and not _is_devnull(value)
        for stream in ("stdout", "stderr")
    )


def functions_reaching_killpg(tree: ast.AST) -> set[str]:
    """Which helpers can actually signal a group — by the call graph, not by the file containing
    the word somewhere.

    `killpg` present in a module says nothing about the runner that needs it: agent-draft has five
    and `run_bounded`, in the same file, could reach none of them. So this walks from the sites
    that genuinely call `os.killpg` outward through callers to a fixpoint, and a runner is
    contained only if it lands in that set.
    """
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    callees, reaching = {}, set()
    for function in functions:
        names = set()
        for node in ast.walk(function):
            if isinstance(node, ast.Call):
                rendered = ast.unparse(node.func)
                names.add(rendered.rsplit(".", 1)[-1])
                if rendered == "os.killpg":
                    reaching.add(function.name)
        callees[function.name] = names
    changed = True
    while changed:
        changed = False
        for name, called in callees.items():
            if name not in reaching and called & reaching:
                reaching.add(name)
                changed = True
    return reaching


def test_every_capturing_launch_site_is_contained_by_its_own_process_group():
    """r32 item 5, enumerated at the only granularity that means anything: the call.

    Both halves are asserted on the SITE, because either alone is a false comfort — and because a
    file-level grep for the two words passes on a module where the Popen that starts a session and
    the helper that kills a group are different helpers that never meet. `start_new_session=True`
    with no reachable killpg leaves an isolated group nobody signals; killpg with no
    `start_new_session` signals the group this process is IN, which includes this process.
    """
    offenders = []
    for path in production_sources():
        tree = ast.parse(path.read_text(errors="replace"))
        _link_parents(tree)
        reaching = functions_reaching_killpg(tree)
        for call in launch_calls(tree):
            if not captures_or_bounds(call):
                continue
            where = f"{path.relative_to(ROOT)}:{call.lineno}"
            api = ast.unparse(call.func)
            if not _is_true(_keyword(call, "start_new_session")):
                offenders.append(f"{where}: {api} captures/bounds without start_new_session=True")
            function = _enclosing_function(call)
            if function is None:
                offenders.append(f"{where}: {api} at module scope — no helper owns the group")
            elif function.name not in reaching:
                offenders.append(f"{where}: {function.name}() can never reach os.killpg")

    assert offenders == [], (
        "capturing launch sites that leak their process group:\n" + "\n".join(offenders)
    )


# --- v16-r34 item 7: the bound must be the DEFAULT, not a thing callers remember ----------------


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_the_primitive_defaults_its_bound_to_the_module_constant(module_path: str):
    """Most callers omit `limit`, so for most callers the default IS the bound.

    A default is evaluated once, at def time, and frozen into `__defaults__` — which is why
    monkeypatching `MAX_CAPTURED_BYTES` does not reach `run_bounded` and why the test doubles that
    let `limit` default to `None` were not merely lax: under them a production signature that had
    quietly dropped or widened its default still passed. This asks the signature directly, so
    weakening the number is a failing test rather than a silent widening at 20-odd call sites.
    """
    ns = load(module_path)
    default = inspect.signature(ns["run_bounded"]).parameters["limit"].default
    assert default is not inspect.Parameter.empty, f"{module_path}: run_bounded(limit=) has no default"
    assert default == ns["MAX_CAPTURED_BYTES"], (
        f"{module_path}: run_bounded defaults limit={default!r}, but the module's bound is "
        f"{ns['MAX_CAPTURED_BYTES']!r} — the default is what most call sites actually get"
    )


@pytest.mark.parametrize("module_path", BOUNDED_CAPTURE_MODULES)
def test_the_run_shaped_wrapper_defaults_its_bound_too(module_path: str):
    """`_bounded_run` is subprocess.run's shape over the same pipe, and the same argument applies:
    every one of deliver's ~20 sites that omits `limit` is bound by this default alone."""
    ns = load(module_path)
    wrapper = ns.get("_bounded_run")
    if wrapper is None:
        pytest.skip(f"{module_path} does not restate the run-shaped wrapper")
    default = inspect.signature(wrapper).parameters["limit"].default
    assert default == ns["MAX_CAPTURED_BYTES"], (
        f"{module_path}: _bounded_run defaults limit={default!r}, not {ns['MAX_CAPTURED_BYTES']!r}"
    )


def test_a_child_one_byte_over_the_bound_is_refused_and_one_byte_under_survives():
    """The boundary itself, against a real child: `>` and not `>=`.

    The adapters simulate this rule, so the rule they simulate has to be pinned to the real
    primitive somewhere, or the simulation is just a second opinion.
    """
    ns = load(AGENT_DRAFT)

    at_bound = ns["run_bounded"](python_says("import sys; sys.stdout.write('x' * 64)"), timeout=60, limit=64)
    assert at_bound.overflowed is False
    assert len(at_bound.stdout) == 64, "exactly the bound must not be an overflow"

    over = ns["run_bounded"](python_says("import sys; sys.stdout.write('x' * 65)"), timeout=60, limit=64)
    assert over.overflowed is True
    assert over.stdout == "", "an overflowing child's bytes are refused, never sliced"
