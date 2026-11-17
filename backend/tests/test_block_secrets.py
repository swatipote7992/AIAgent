"""Tests for the Claude Code secrets hook (.claude/hooks/block_secrets.py).

Run from backend/ with the virtual environment active:  python -m pytest

The hook receives a tool call as JSON on stdin; exit code 2 means blocked, 0 means allowed.
Fake secrets are built at run time so this file holds nothing that looks like a secret (the hook
would block writing it otherwise). The git cases run in a temporary repository, so the result
does not depend on the state of the real working folder.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "block_secrets.py"

FAKE = "A1b2C3d4" * 4
HEX = "0123456789abcdef" * 2
CONN = "Instrumentation" + "Key=" + "-".join(["00000000", "1111", "2222", "3333", "444444444444"])
KEY_NAME = "API" + "_KEY"

BLOCKED = 2
ALLOWED = 0


def run_hook(tool: str, data: dict, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": tool, "tool_input": data}),
        capture_output=True, text=True, cwd=cwd, check=False,
    )


def assert_blocked(tool: str, data: dict, cwd: Path | None = None) -> None:
    done = run_hook(tool, data, cwd)
    assert done.returncode == BLOCKED, f"expected a block, got exit {done.returncode}"
    assert "BLOCKED" in done.stderr
    for secret in (FAKE, HEX, CONN):  # the message must never repeat the secret
        assert secret not in done.stderr


def assert_allowed(tool: str, data: dict, cwd: Path | None = None) -> None:
    done = run_hook(tool, data, cwd)
    assert done.returncode == ALLOWED, f"expected allowed, got exit {done.returncode}: {done.stderr}"


def test_hook_file_exists():
    assert HOOK.is_file(), f"hook not found at {HOOK}"


# ---- commands that would print secrets ----

@pytest.mark.parametrize("tool, command", [
    ("Bash", "cat backend/.env"),
    ("PowerShell", "Get-Content .env"),
    ("Bash", "printenv"),
    ("Bash", "echo $" + KEY_NAME),
    ("Bash", "az cognitiveservices account keys list-keys -n x"),
    ("Bash", "az containerapp secret show --name a -g b"),
    ("Bash", "az staticwebapp secrets list --name insur-rag-web"),
])
def test_commands_that_print_secrets_are_blocked(tool, command):
    assert_blocked(tool, {"command": command})


@pytest.mark.parametrize("command", [
    "cat .env.example",
    "ls backend",
    "az containerapp update --name a --remove-env-vars X",
])
def test_ordinary_commands_are_allowed(command):
    assert_allowed("Bash", {"command": command})


# ---- files that would contain secrets ----

@pytest.mark.parametrize("tool, data", [
    ("Write", {"file_path": "notes.md", "content": f"set {KEY_NAME}={FAKE}"}),
    ("Edit", {"file_path": "x.py", "new_string": f'password = "{FAKE}"'}),
    ("MultiEdit", {"file_path": "x.py", "edits": [{"new_string": f"secret = '{FAKE}'"}]}),
    ("Write", {"file_path": "notes.txt", "content": CONN}),
    ("Write", {"file_path": "README.md", "content": "token is " + HEX}),
])
def test_writes_with_secrets_are_blocked(tool, data):
    assert_blocked(tool, data)


@pytest.mark.parametrize("data", [
    {"file_path": "README.md", "content": f"set {KEY_NAME}=<your key here>"},
    {"file_path": "README.md", "content": "Revision insur-rag-api--0000004 is healthy."},
    {"file_path": "notes.md", "content": "hash " + HEX[:20]},
    {"file_path": "a.py", "content": "def f():\n    return 1\n"},
    {"file_path": ".env", "content": f"AZURE_SEARCH_KEY={FAKE}"},
    {"file_path": ".env.example", "content": "AZURE_SEARCH_KEY=your-search-key-here"},
])
def test_safe_writes_are_allowed(data):
    assert_allowed("Write", data)


# ---- git commands, in a temporary repository ----

def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "README.md").write_text("hello\n")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{}\n")
    return tmp_path


@pytest.mark.parametrize("command", ["git add .env", "git add .claude/settings.json"])
def test_adding_env_or_claude_files_by_name_is_blocked(repo, command):
    assert_blocked("Bash", {"command": command}, repo)


def test_adding_a_normal_file_is_allowed(repo):
    assert_allowed("Bash", {"command": "git add README.md"}, repo)


@pytest.mark.parametrize("command", ["git add .", "git add -A", "git add --all"])
def test_bulk_add_is_blocked_while_claude_files_are_untracked(repo, command):
    assert_blocked("Bash", {"command": command}, repo)


def test_bulk_add_is_allowed_when_nothing_forbidden_is_untracked(repo):
    (repo / ".claude" / "settings.json").unlink()
    (repo / ".claude").rmdir()
    assert_allowed("Bash", {"command": "git add ."}, repo)


def test_commit_with_a_staged_claude_file_is_blocked(repo):
    git(repo, "add", "-f", ".claude/settings.json")
    assert_blocked("Bash", {"command": "git commit -m test"}, repo)


def test_commit_whose_diff_adds_a_secret_is_blocked(repo):
    (repo / "config.py").write_text(f'password = "{FAKE}"\n')
    git(repo, "add", "config.py")
    assert_blocked("Bash", {"command": "git commit -m test"}, repo)


def test_clean_commit_is_allowed(repo):
    git(repo, "add", "README.md")
    assert_allowed("Bash", {"command": "git commit -m test"}, repo)


# ---- robustness ----

def test_unreadable_input_never_blocks():
    done = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True, check=False)
    assert done.returncode == ALLOWED


def test_other_tools_are_ignored():
    assert_allowed("Read", {"file_path": ".env"})
