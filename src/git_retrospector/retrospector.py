#!/usr/bin/env python3
import subprocess
import os
import sys
import argparse
from git_retrospector.parser import parse_test_results
import toml
from pydantic import ValidationError
from git_retrospector.config import Config  # Import the Config class
from git_retrospector.git_utils import get_original_branch, get_current_commit_hash  # Import Git utility functions
from git_retrospector.runners import run_vitest, run_playwright  # Import test runner functions


def process_commit(target_repo, commit_hash, output_dir, origin_branch, config):
    """
    Checks out a specific commit in the target repository, runs tests, and returns to the original branch.

    Args:
        target_repo (str): The path to the target repository.
        commit_hash (str): The hash of the commit to process.
        output_dir (str): The base output directory.
        origin_branch (str): The original branch to return to.
        config (Config): The configuration object.
    """
    test_output_dir = str(config.test_result_dir)

    output_dir_for_commit = os.path.join(test_output_dir, commit_hash)
    os.makedirs(output_dir_for_commit, exist_ok=True) # Create directory

    vitest_output = os.path.join(output_dir_for_commit, "vitest.xml")
    playwright_output = os.path.join(output_dir_for_commit, "playwright.xml")

    print(f"Processing commit {commit_hash}")

    if os.path.exists(vitest_output) and os.path.exists(playwright_output):
        print("  Skipping - output files exist")
        return

    if origin_branch is None:
        print("  Cannot checkout original branch (not determined). Skipping checkout.")
        return

    try:
        subprocess.run(
            ["git", "checkout", "--force", commit_hash],
            cwd=target_repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"  Failed to checkout commit: {commit_hash}", file=sys.stderr)
        return

    run_vitest(target_repo, output_dir_for_commit, config)
    run_playwright(target_repo, output_dir_for_commit, config)

    try:
        subprocess.run(
            ["git", "checkout", "--force", origin_branch],
            cwd=target_repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"  Failed to checkout original branch", file=sys.stderr)
        return

def run_tests(target_name, iteration_count):
    """
    Runs tests on a range of commits in the target repository.

    Args:
        target_name (str): The name of the target repository (used to locate the config file).
        iteration_count (int): The number of commits to go back in history.
    """
    print(f"Script started")
    print(f"Target repository: {target_name}")

    # Load config
    config_file_path = os.path.join("retros", target_name, "config.toml")
    try:
        with open(config_file_path, "r") as config_file:
            config_data = toml.load(config_file)
        config = Config(**config_data)
        target_repo = str(config.source_dir)  # Convert Path to string
        test_output_dir = str(config.test_result_dir)

    except (FileNotFoundError, KeyError, toml.TomlDecodeError) as e:
        print(f"  Error loading config.toml for target: {target_name}: {config_file_path}: {e}")
        return
    except ValidationError as e:
        print(f"  Error validating config.toml for target: {target_name}: {config_file_path}: {e}")
        return

    print(f"Output directory: {test_output_dir}")
    print(f"Running tests for {iteration_count} commits")
    print(f"Target repository: {target_repo}")


    origin_branch = get_original_branch(target_repo)  # Get original branch of the *target* repo
    if origin_branch is None:
      print("Could not determine original branch.  Using HEAD~{i} relative to current commit.")

    # Check if target_repo is a git repository
    if get_current_commit_hash(target_repo) is None:
        print(f"Error: Target repo directory {target_repo} is not a git repository or does not exist", file=sys.stderr)
        return

    for i in range(iteration_count):
        try:
            # Use get_current_commit_hash to get the initial HEAD
            current_commit = get_current_commit_hash(target_repo)
            if current_commit is None:
                print("Failed to get current commit hash. Exiting.")
                return

            commit_hash_result = subprocess.run(
                ["git", "rev-parse", "--short", f"{current_commit}~{i}"],
                cwd=target_repo,
                capture_output=True,
                text=True,
                check=True,
            )
            commit_hash = commit_hash_result.stdout.strip()
            if not commit_hash:
                print(
                    f"Error: rev-parse returned empty string for commit {current_commit}~{i}"
                )
                continue  # Skip this iteration
            assert origin_branch is not None, "Failed to determine original branch"
            process_commit(target_repo, commit_hash, test_output_dir, origin_branch, config)

        except subprocess.CalledProcessError as e:
            print(f"Error getting commit hash: {e}", file=sys.stderr)
            continue

    print(f"Test runs completed. Results stored in {test_output_dir}")


def initialize(target_name, source_dir, output_base_dir="retros"):
    """
    Initializes the target-specific directory and config file.

    Args:
        target_name (str): The name of the target repository.
        source_dir (str): The path to the target repository.
        output_base_dir (str, optional): The base directory for retrospectives. Defaults to "retros".
    """
    config_file_path = os.path.join(output_base_dir, target_name, "config.toml")
    if not os.path.exists(config_file_path):
        config = Config(name=target_name, source_dir=os.getcwd(), output_paths={
                "vitest": "test-output/vitest.xml",
                "playwright": "test-output/playwright.xml",
            })
        print(f"config_data: {config}")
        # Convert Path objects to strings for TOML serialization
        config_data = config.model_dump()
        config_data['source_dir'] = str(config_data['source_dir'])
        config_data['test_result_dir'] = str(config_data['test_result_dir'])
        with open(config_file_path, "w") as config_file:
            toml.dump(config_data, config_file)
    return config_file_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run tests on a range of commits and parse results.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'init' command
    init_parser = subparsers.add_parser("init", help="Initialize a target repository")
    init_parser.add_argument("target_name", help="Name of the target repository")
    init_parser.add_argument("source_dir", help="Path to the target repository")

    # 'run' command
    run_parser = subparsers.add_parser("run", help="Run tests on a target repository")
    run_parser.add_argument(
        "target_name", help="Name of the target repository (must be initialized first)"
    )
    run_parser.add_argument(
        "-i",
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations (default: 10)",
    )
    run_parser.add_argument(
        "-c", "--commit_dir", help="Specific commit directory to process"
    )

    args = parser.parse_args()

    if args.command == "init":
        initialize(args.target_name, args.source_dir)
    elif args.command == "run":
        run_tests(args.target_name, args.iterations)
        # parse_test_results(
        #     args.commit_dir,
        #     results_dir=os.path.join("retros", args.target_name, "test-output"),
        # )  # Call parse_test_results with the commit_dir
    else:
        parser.print_help()
