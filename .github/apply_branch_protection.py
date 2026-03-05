"""Apply branch protection rules from branch_protection.json via GitHub API.

Usage:
    python .github/apply_branch_protection.py --token YOUR_PAT

How to get a Personal Access Token (PAT):
    GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
    Required scope: repo (full control of private repositories)
    OR for public repos: public_repo
"""

import argparse
import json
import sys
from pathlib import Path

import requests


CONFIG_PATH = Path(__file__).parent / "branch_protection.json"
GITHUB_API = "https://api.github.com"


def apply_protection(repo: str, branch: str, rules: dict, token: str) -> None:
    """Apply branch protection rules for a single branch.

    Args:
        repo: Repository in format 'owner/repo'.
        branch: Branch name to protect.
        rules: Protection rules dict matching GitHub API schema.
        token: GitHub Personal Access Token.

    Raises:
        requests.HTTPError: If the API request fails.
    """
    url = f"{GITHUB_API}/repos/{repo}/branches/{branch}/protection"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = requests.put(url, json=rules, headers=headers, timeout=15)

    if response.status_code == 200:
        print(f"  [OK] {branch}: protection applied")
    else:
        print(f"  [FAIL] {branch}: HTTP {response.status_code}")
        print(f"         {response.json().get('message', response.text)}")
        response.raise_for_status()


def main() -> None:
    """Entry point: parse args, load config, apply all rules."""
    parser = argparse.ArgumentParser(description="Apply GitHub branch protection from JSON config")
    parser.add_argument("--token", required=True, help="GitHub Personal Access Token")
    args = parser.parse_args()

    if not CONFIG_PATH.exists():
        print(f"Config not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    with CONFIG_PATH.open(encoding="utf-8") as f:
        config: dict = json.load(f)

    repo: str = config["repo"]
    branches: dict = config["branches"]

    print(f"Applying branch protection for: {repo}")

    errors = 0
    for branch, rules in branches.items():
        try:
            apply_protection(repo, branch, rules, args.token)
        except requests.HTTPError:
            errors += 1

    if errors:
        print(f"\n{errors} branch(es) failed. Check token permissions (scope: repo).")
        sys.exit(1)
    else:
        print("\nAll branches protected successfully.")


if __name__ == "__main__":
    main()
