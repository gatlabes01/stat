from __future__ import annotations

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def restore_deleted_tracked(
    root: Path, rel: str, *, allow_delete: list[str] | None = None
) -> None:
    """Put back tracked files that vanished, except paths we meant to remove."""
    allow = {p.replace("\\", "/").strip("/") for p in (allow_delete or [])}
    listed = _run(["git", "ls-files", "-d", "--", rel], root)
    for line in listed.stdout.splitlines():
        path = line.strip().replace("\\", "/")
        if not path:
            continue
        if any(path == d or path.startswith(d + "/") for d in allow):
            continue
        _run(["git", "checkout", "HEAD", "--", path], root)


def git_add_keep(
    root: Path,
    rel: str,
    *,
    force: bool = False,
    allow_delete: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Stage new and changed files. Stage deletions only for allow_delete paths."""
    restore_deleted_tracked(root, rel, allow_delete=allow_delete)
    cmd = ["git", "add", "--ignore-removal"]
    if force:
        cmd.append("-f")
    cmd.append(rel)
    add = _run(cmd, root)
    if add.returncode != 0:
        return add
    for extra in allow_delete or []:
        gone = _run(["git", "add", "-A", "--", extra], root)
        if gone.returncode != 0:
            err = (gone.stderr or gone.stdout or "").lower()
            if "did not match" in err or "pathspec" in err:
                continue
            return gone
    return add
