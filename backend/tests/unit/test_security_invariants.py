"""Repository-level security invariants (docs/nl-to-sql.md)."""

import re
from pathlib import Path

from olist_nlsql.dbsetup.env import REPO_ROOT

SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    ".terraform",
    "data",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".ts",
    ".tsx",
    ".tf",
    ".sql",
    ".txt",
    ".example",
    ".cfg",
    ".ini",
}
SECRET_PATTERNS = {
    "aws access key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "aws secret assignment": re.compile(r"aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+]{40}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "account-scoped arn": re.compile(r"arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{12}:"),
}


def _repo_files() -> list[Path]:
    files = []
    for path in REPO_ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        if path.is_file() and (path.suffix in TEXT_SUFFIXES or path.name.startswith(".env.")):
            files.append(path)
    return files


def test_no_credentials_in_the_repository() -> None:
    this_file = Path(__file__).resolve()
    hits = [
        f"{path.relative_to(REPO_ROOT)}: {name}"
        for path in _repo_files()
        if path.resolve() != this_file
        for name, pattern in SECRET_PATTERNS.items()
        if pattern.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert not hits, hits


def test_env_file_is_git_ignored() -> None:
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored and "data/raw/" in ignored


def test_env_example_holds_no_aws_credentials() -> None:
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "AWS_ACCESS_KEY_ID" not in example and "AWS_SECRET_ACCESS_KEY" not in example
