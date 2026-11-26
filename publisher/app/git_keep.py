from __future__ import annotations

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def restore_deleted_tracked(root: Path, rel: str) -> None:
    """Put back any tracked files under rel that vanished from the working tree."""
    listed = _run(["git", "ls-files", "-d", "--", rel], root)
    for line in listed.stdout.splitlines():
        path = line.strip()
        if path:
            _run(["git", "checkout", "HEAD", "--", path], root)


def git_add_keep(root: Path, rel: str, *, force: bool = False) -> subprocess.CompletedProcess:
    """Stage new and changed files only. Never stage deletions."""
    restore_deleted_tracked(root, rel)
    cmd = ["git", "add", "--ignore-removal"]
    if force:
        cmd.append("-f")
    cmd.append(rel)
    return _run(cmd, root)
