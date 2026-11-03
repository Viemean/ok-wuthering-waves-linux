#!/usr/bin/env python3
"""Synchronize runtime assets and developer templates from official upstream.

Usage:
    python .bin/sync_assets.py              # Synchronize runtime assets/
    python .bin/sync_assets.py --templates  # Pull ok_templates/ (840MB raw 4K templates for annotation)
    python .bin/sync_assets.py --all        # Synchronize both assets/ and ok_templates/
    python .bin/sync_assets.py --check      # Check status against tracked upstream version
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRACKING_FILE = PROJECT_ROOT / ".agents" / "upstream_tracking.json"
DEFAULT_UPSTREAM_URL = "https://github.com/ok-oldking/ok-wuthering-waves.git"


def get_tracked_ref() -> str:
    """Read target commit/tag from upstream_tracking.json."""
    if TRACKING_FILE.is_file():
        try:
            with open(TRACKING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("business_upstream", {}).get("last_synced_commit", "master")
        except Exception as e:
            print(f"[WARN] Failed to read upstream_tracking.json: {e}")
    return "master"


def ensure_upstream_remote(repo_url: str = DEFAULT_UPSTREAM_URL) -> str:
    """Ensure upstream git remote exists."""
    remotes = subprocess.check_output(
        ["git", "remote"], cwd=PROJECT_ROOT, text=True
    ).splitlines()
    if "upstream" not in remotes:
        subprocess.check_call(
            ["git", "remote", "add", "upstream", repo_url], cwd=PROJECT_ROOT
        )
        print(f"[INFO] Added git remote 'upstream' -> {repo_url}")
    return "upstream"


def sync_path_from_upstream(target_path: str, ref: str):
    """Fetch and checkout a specific directory from upstream without full tree merge."""
    remote = ensure_upstream_remote()
    print(f"[INFO] Fetching upstream ref '{ref}' for path '{target_path}'...")

    # Fetch target commit/tag with shallow depth to minimize download size
    subprocess.check_call(
        ["git", "fetch", remote, ref, "--depth=1"], cwd=PROJECT_ROOT
    )

    fetch_head = "FETCH_HEAD"
    print(f"[INFO] Restoring '{target_path}' from upstream {ref}...")
    subprocess.check_call(
        ["git", "checkout", fetch_head, "--", target_path], cwd=PROJECT_ROOT
    )
    print(f"[SUCCESS] '{target_path}' synchronized successfully with upstream {ref}.")


def check_status(ref: str):
    """Check difference between local files and upstream ref."""
    remote = ensure_upstream_remote()
    subprocess.check_call(["git", "fetch", remote, ref, "--depth=1"], cwd=PROJECT_ROOT)
    print(f"[INFO] Comparing local 'assets/' with upstream '{ref}'...")
    diff_output = subprocess.check_output(
        ["git", "diff", "--stat", "FETCH_HEAD", "--", "assets"],
        cwd=PROJECT_ROOT,
        text=True,
    )
    if diff_output.strip():
        print("[INFO] Differences found in assets:\n", diff_output)
    else:
        print("[SUCCESS] Local 'assets/' is identical to upstream.")


def main():
    parser = argparse.ArgumentParser(
        description="Sync assets and templates from upstream ok-wuthering-waves repository."
    )
    parser.add_argument(
        "--ref",
        type=str,
        default=None,
        help="Upstream git ref (commit hash, tag, or branch). Defaults to upstream_tracking.json cursor.",
    )
    parser.add_argument(
        "--templates",
        action="store_true",
        help="Sync ok_templates/ (raw 4K developer templates, ~840MB).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Sync both assets/ and ok_templates/.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check differences against upstream without overwriting local files.",
    )
    args = parser.parse_args()

    ref = args.ref or get_tracked_ref()
    print(f"[INFO] Target upstream ref: {ref}")

    if args.check:
        check_status(ref)
        return

    if args.all:
        sync_path_from_upstream("assets", ref)
        sync_path_from_upstream("ok_templates", ref)
    elif args.templates:
        sync_path_from_upstream("ok_templates", ref)
    else:
        # Default behavior: sync runtime assets only
        sync_path_from_upstream("assets", ref)


if __name__ == "__main__":
    main()
