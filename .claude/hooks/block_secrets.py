"""PreToolUse hook: stop secrets from being committed, printed or written into files.

Enforces constitution principles IV (secrets never printed or logged) and V (no credentials in git).
Claude Code sends the tool call as JSON on stdin. Exit code 2 blocks the call and the reason on
stderr is shown to Claude. Exit code 0 allows it. The hook never prints the secret itself, only
which rule was hit.

Blocked:
  Bash   - git add / git commit that would include .env or .claude/ files, or a staged diff that
           adds something that looks like a secret
  Bash   - commands that print .env or fetch secrets (az ... list-keys, secrets list/show, deployment tokens)
  Write/Edit - content that looks like a real key, token or connection string
             (README.md is checked more strictly: any long hex or base64-like string)
"""
import json
import re
import subprocess
import sys

# A value this long next to a secret-sounding name is treated as a real secret.
KEYWORD_ASSIGNMENT = re.compile(
    r"""(?ix)
    (api[_-]?key|access[_-]?key|secret|token|password|passwd|connection[_-]?string|subscription[_-]?key)
    ["']?\s*[:=]\s*["']?([A-Za-z0-9+/_\-=.]{20,})
    """
)
KNOWN_FORMATS = {
    "Application Insights connection string": re.compile(r"InstrumentationKey=[0-9a-fA-F-]{36}"),
    "storage or service bus key": re.compile(r"(AccountKey|SharedAccessKey)=[A-Za-z0-9+/=]{20,}"),
    "OpenAI-style secret key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
# Stricter, README only: long hex (32+) or long base64-like strings (40+).
README_LONG_STRING = re.compile(r"(?<![A-Za-z0-9+/_\-])([0-9a-fA-F]{32,}|[A-Za-z0-9+/_\-]{40,}={0,2})(?![A-Za-z0-9+/_\-])")
PLACEHOLDER = re.compile(r"(?i)your|<|>|xxx|\.\.\.|placeholder|changeme|example|\$\{?\w+|%\w+%|\*{3,}")

PRINT_SECRET_COMMANDS = [
    (re.compile(r"(?i)\b(cat|type|head|tail|less|more|bat|grep|rg|findstr|Get-Content|gc|Select-String|sls)\b[^|;&\n]*\.env(?!\.example)\b"),
     "reading the .env file prints every secret in it"),
    (re.compile(r"(?i)\b(printenv|Get-ChildItem\s+env:|gci\s+env:|dir\s+env:)|(^|[;&|]\s*)(env|set)\s*($|[;&|])"),
     "listing environment variables prints secrets"),
    (re.compile(r"(?i)\b(echo|Write-Host|Write-Output|printf)\b[^|;&\n]*(\$env:|\$\{?|%)\w*(KEY|TOKEN|SECRET|PASSWORD|CONNECTION)\w*"),
     "echoing a variable that holds a secret"),
    (re.compile(r"(?i)\baz\b.*\b(list-keys|list-keys|regenerate-key|show-keys)\b"),
     "this az command returns keys"),
    (re.compile(r"(?i)\baz\s+(containerapp|staticwebapp)\s+secrets?\s+(show|list)\b(?!.*--query\s+\"?\[?\*?\]?\.?name)"),
     "this az command returns secret values (use --query with only the secret names)"),
    (re.compile(r"(?i)\bdeployment[-_ ]?token\b|\bsecrets\s+list\b.*--name\s+insur-rag-web"),
     "deployment tokens must not be printed"),
    (re.compile(r"(?i)--show-secrets?\b"),
     "--show-secrets prints secret values"),
]

BULK_ADD = re.compile(r"(?i)\bgit\s+add\b[^|;&\n]*(\s-A\b|\s--all\b|\s\.(\s|$)|\s:/|\s-u\b)")
GIT_ADD = re.compile(r"(?i)\bgit\s+add\b")
GIT_COMMIT = re.compile(r"(?i)\bgit\s+commit\b")
FORBIDDEN_PATH = re.compile(r"(^|[\s/\\\"'])(\.env(\.[A-Za-z0-9_-]+)?(?!\.example)|\.claude[/\\])")


def block(reason: str) -> None:
    print(f"BLOCKED by secrets hook: {reason}", file=sys.stderr)
    sys.exit(2)


def git(*args: str) -> str:
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True, timeout=20)
        return done.stdout if done.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def is_forbidden_path(path: str) -> bool:
    path = path.replace("\\", "/").strip()
    if path.endswith(".env.example"):
        return False
    return path == ".env" or path.endswith("/.env") or ".env." in path.split("/")[-1] and path.split("/")[-1].startswith(".env") or path.startswith(".claude/") or "/.claude/" in path


def looks_like_secret(text: str, strict: bool) -> str:
    for name, pattern in KNOWN_FORMATS.items():
        if pattern.search(text):
            return name
    for match in KEYWORD_ASSIGNMENT.finditer(text):
        if not PLACEHOLDER.search(match.group(0)):
            return f"a long value assigned to '{match.group(1)}'"
    if strict:
        for match in README_LONG_STRING.finditer(text):
            value = match.group(1)
            if PLACEHOLDER.search(value) or "/" in value and value.count("/") > 2:
                continue
            if re.fullmatch(r"[0-9a-fA-F]{32,}", value) or (len(value) >= 40 and re.search(r"\d", value) and re.search(r"[A-Za-z]", value)):
                return "a long hex or base64-like string"
    return ""


def check_bash(command: str) -> None:
    for pattern, why in PRINT_SECRET_COMMANDS:
        if pattern.search(command):
            block(f"{why}. Read the value into a variable and mask it, or ask the owner to run it.")

    if GIT_ADD.search(command):
        parts = re.split(r"[;&|]+", command)
        for part in parts:
            if GIT_ADD.search(part) and any(is_forbidden_path(tok.strip("\"'")) for tok in part.split()):
                block("git add of .env or .claude/ files. Constitution V: credentials and agent folders are never committed without review.")
        if BULK_ADD.search(command):
            untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
            hits = [p for p in untracked if is_forbidden_path(p)]
            if hits:
                block(f"a bulk 'git add' would stage {len(hits)} file(s) under .claude/ or .env. Add files by name, or review .claude/ first.")

    if GIT_COMMIT.search(command):
        staged = git("diff", "--cached", "--name-only").splitlines()
        hits = [p for p in staged if is_forbidden_path(p)]
        if hits:
            block(f"the staged changes include {len(hits)} file(s) under .claude/ or .env. Unstage them with 'git restore --staged <file>'.")
        added = "\n".join(l[1:] for l in git("diff", "--cached", "-U0").splitlines() if l.startswith("+") and not l.startswith("+++"))
        found = looks_like_secret(added, strict=False)
        if found:
            block(f"the staged diff adds something that looks like a secret ({found}). Find it with 'git diff --cached' and remove it.")


def check_write(path: str, text: str) -> None:
    normalized = path.replace("\\", "/")
    name = normalized.split("/")[-1]
    if name == ".env" or name.endswith(".env.example") or normalized.endswith("block_secrets.py"):
        return
    found = looks_like_secret(text, strict=(name.lower() == "readme.md"))
    if found:
        block(f"this write to {name} contains something that looks like a secret ({found}). Use a placeholder or the file path instead.")


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # not a call we understand; never block on a parsing problem
    tool = event.get("tool_name", "")
    data = event.get("tool_input", {}) or {}
    if tool == "Bash":
        check_bash(data.get("command", ""))
    elif tool == "PowerShell":
        check_bash(data.get("command", ""))
    elif tool in ("Write", "Edit", "MultiEdit"):
        path = data.get("file_path", "")
        text = data.get("content") or data.get("new_string") or ""
        for edit in data.get("edits", []) or []:
            text += "\n" + edit.get("new_string", "")
        check_write(path, text)
    sys.exit(0)


if __name__ == "__main__":
    main()
