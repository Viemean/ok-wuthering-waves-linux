import os
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple

from ok.util.file import get_path_relative_to_exe
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)

DEFAULT_UPSTREAM_URL = "https://github.com/Viemean/ok-wuthering-waves-linux.git"
DEFAULT_BRANCH = "linux-support"
FETCH_DEPTH = 5


def get_git_root(cwd: Optional[str] = None) -> Optional[str]:
    """Finds the root directory of the git repository."""
    base_dir = cwd or get_path_relative_to_exe("")
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=base_dir,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if output and os.path.isdir(output):
            return output
    except Exception:
        pass
    if os.path.isdir(os.path.join(base_dir, ".git")):
        return base_dir
    return None


def is_git_repository(cwd: Optional[str] = None) -> bool:
    """Checks whether the current working directory is inside a git repository."""
    return get_git_root(cwd) is not None


def is_shallow_repository(repo_dir: Optional[str] = None) -> bool:
    """Checks whether the git repository is a shallow clone."""
    root = get_git_root(repo_dir)
    if not root:
        return False
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return output.lower() == "true"
    except Exception:
        return False


def is_developer_repository(repo_dir: Optional[str] = None) -> bool:
    """Checks whether the repository is a development environment."""
    root = get_git_root(repo_dir)
    if not root:
        return False
    try:
        output = subprocess.check_output(
            ["git", "remote"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        remotes = [r.strip() for r in output.splitlines() if r.strip()]
        if len(remotes) > 1 or "upstream" in remotes:
            return True
    except Exception:
        pass
    return False


def build_fetch_command(
    upstream_url: str,
    target_branch: str,
    depth: int = FETCH_DEPTH,
    repo_dir: Optional[str] = None,
) -> List[str]:
    """Builds git fetch command arguments based on repository state."""
    cmd = ["git", "fetch"]
    if is_shallow_repository(repo_dir) and not is_developer_repository(repo_dir):
        cmd.append(f"--depth={depth}")
    cmd.extend([upstream_url, target_branch])
    return cmd


def get_current_commit(repo_dir: Optional[str] = None) -> str:
    """Gets the current HEAD commit hash."""
    root = get_git_root(repo_dir)
    if not root:
        return ""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def get_current_branch(repo_dir: Optional[str] = None) -> str:
    """Gets the current git branch name."""
    root = get_git_root(repo_dir)
    if not root:
        return DEFAULT_BRANCH
    try:
        branch = subprocess.check_output(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if branch:
            return branch
    except Exception:
        pass
    return DEFAULT_BRANCH


def check_git_updates(
    repo_dir: Optional[str] = None,
    upstream_url: str = DEFAULT_UPSTREAM_URL,
    branch: Optional[str] = None,
    depth: int = FETCH_DEPTH,
) -> Tuple[bool, List[str], str]:
    """Checks for updates against upstream repository.

    Returns:
        (has_update: bool, commit_notes: List[str], remote_commit_or_status: str)
    """
    root = get_git_root(repo_dir)
    if not root:
        return False, [], "Not a valid git repository"

    target_branch = branch or get_current_branch(root)
    local_commit = get_current_commit(root)

    try:
        fetch_cmd = build_fetch_command(upstream_url, target_branch, depth, root)
        subprocess.check_call(
            fetch_cmd,
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.error(f"git fetch failed: {e}")
        return False, [], f"git fetch error: {e}"

    try:
        fetch_head = subprocess.check_output(
            ["git", "rev-parse", "FETCH_HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception as e:
        return False, [], f"Cannot resolve FETCH_HEAD: {e}"

    if local_commit == fetch_head:
        return False, [], "Already up to date"

    notes = []
    try:
        log_output = subprocess.check_output(
            ["git", "log", f"{local_commit}..FETCH_HEAD", f"-n{depth}", "--oneline"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if log_output:
            notes = [line.strip() for line in log_output.splitlines() if line.strip()]
    except Exception:
        pass

    if not notes:
        try:
            log_output = subprocess.check_output(
                ["git", "log", "FETCH_HEAD", f"-n{depth}", "--oneline"],
                cwd=root,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if log_output:
                notes = [line.strip() for line in log_output.splitlines() if line.strip()]
        except Exception:
            pass

    return True, notes, fetch_head


def get_local_commits(repo_dir: Optional[str] = None, count: int = FETCH_DEPTH) -> List[dict]:
    """Gets recently pulled local commits up to count."""
    root = get_git_root(repo_dir)
    if not root:
        return []
    try:
        head = get_current_commit(root)
        output = subprocess.check_output(
            ["git", "log", f"-n{count}", "--format=%H|%h|%s"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        commits = []
        if output:
            for line in output.splitlines():
                if not line.strip() or "|" not in line:
                    continue
                parts = line.split("|", 2)
                if len(parts) == 3:
                    full_hash, short_hash, msg = parts
                    commits.append({
                        "hash": full_hash,
                        "short_hash": short_hash,
                        "message": msg,
                        "is_head": (full_hash == head),
                    })
        return commits
    except Exception as e:
        logger.error(f"Failed to get local commits: {e}")
        return []


def pull_git_updates(
    repo_dir: Optional[str] = None,
    upstream_url: str = DEFAULT_UPSTREAM_URL,
    branch: Optional[str] = None,
    depth: int = FETCH_DEPTH,
    target_commit: Optional[str] = None,
) -> Tuple[bool, str]:
    """Pulls updates by fetching and resetting to FETCH_HEAD or target_commit."""
    root = get_git_root(repo_dir)
    if not root:
        return False, "Not a valid git repository"

    target_branch = branch or get_current_branch(root)
    try:
        if target_commit:
            subprocess.check_call(
                ["git", "reset", "--hard", target_commit],
                cwd=root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, "Success"

        fetch_cmd = build_fetch_command(upstream_url, target_branch, depth, root)
        subprocess.check_call(
            fetch_cmd,
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            ["git", "reset", "--hard", "FETCH_HEAD"],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True, "Success"
    except Exception as e:
        logger.error(f"Failed to pull git updates: {e}")
        return False, str(e)


def restart_with_uv(repo_dir: Optional[str] = None) -> None:
    """Restarts application using uv run python main.py and exits current process."""
    root = get_git_root(repo_dir) or get_path_relative_to_exe("")
    uv_bin = shutil.which("uv") or "uv"
    cmd = [uv_bin, "run", "python", "main.py"]
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])

    logger.info(f"Restarting application with uv: {cmd} (cwd={root})")
    subprocess.Popen(cmd, cwd=root, start_new_session=True)
    os._exit(0)
