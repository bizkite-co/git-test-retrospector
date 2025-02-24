#!/usr/bin/env python3
import subprocess
import os
import sys

def get_original_branch(target_repo):
    """Gets the original Git branch of the repository.

    Args:
        target_repo (str): Path to the Git repository.

    Returns:
        str: The original branch name, or None if an error occurs.
    """
    try:
        result = subprocess.run(
            ['git', 'symbolic-ref', '--short', 'HEAD'],
            cwd=target_repo,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"Original branch: {result.stdout.strip()}")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting original branch: {e}", file=sys.stderr)
        return None


def get_current_commit_hash(target_repo):
    """Gets the current commit hash of the repository.

    Args:
        target_repo (str): Path to the Git repository.

    Returns:
        str: The current commit hash, or None if an error occurs.
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=target_repo,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting current commit hash: {e}", file=sys.stderr)
        return None
