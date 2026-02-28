"""GitHub wrapper — thin layer over `gh` CLI.

Usage (from agent's Python runtime):
    from libs import github

    # List your own repos
    repos = github.list_repos()

    # Search issues
    issues = github.search_issues("is:open label:bug", repo="surya1729/my-repo")

    # Get issue details
    issue = github.get_issue("surya1729/my-repo", 42)

    # List PRs
    prs = github.list_prs("surya1729/my-repo", state="open")

    # Get PR with diff stats
    pr = github.get_pr("surya1729/my-repo", 123)

    # Get recent commits
    commits = github.list_commits("surya1729/my-repo", branch="main", limit=10)

    # Get workflow runs (CI)
    runs = github.list_runs("surya1729/my-repo", limit=5)

    # Get check status for a PR
    checks = github.get_checks("surya1729/my-repo", 123)
"""

import json
import subprocess
import os
import re
from datetime import datetime
from pathlib import Path

# Disable colors in gh CLI output for JSON parsing
os.environ['CLICOLOR'] = '0'

_LOG = Path(__file__).parent.parent / "logs" / "libs_calls.log"


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    _LOG.parent.mkdir(exist_ok=True)
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def _gh(*args) -> str:
    """Run gh CLI command, return stdout."""
    _log(f"  gh {' '.join(args)}")
    result = subprocess.run(
        ["gh", *args],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}... failed: {result.stderr.strip()}")
    # Strip ANSI color codes in case they're still present
    return _strip_ansi(result.stdout.strip())


def _gh_json(*args) -> list | dict:
    """Run gh CLI command, parse JSON output."""
    raw = _gh(*args)
    if not raw:
        return []
    return json.loads(raw)


def _normalize_item(item: dict) -> dict:
    """Flatten nested gh objects: author → string, labels → list of strings."""
    if isinstance(item.get("author"), dict):
        item["author"] = item["author"].get("login", "")
    if isinstance(item.get("labels"), list) and item["labels"] and isinstance(item["labels"][0], dict):
        item["labels"] = [l.get("name", "") for l in item["labels"]]
    return item


# --- Repos ---

def list_repos(limit: int = 30) -> list[dict]:
    """List the authenticated user's own repos.
    Returns [{name, description, isPrivate, updatedAt, url}]."""
    _log(f"github.list_repos(limit={limit}) called")
    result = _gh_json("repo", "list", "--limit", str(limit), "--json", "name,description,isPrivate,updatedAt,url")
    _log(f"  -> returned {len(result)} repos")
    return result


# --- Issues ---

def search_issues(query: str, repo: str = None, limit: int = 20) -> list[dict]:
    """Search issues. Returns [{number, title, author, state, labels, createdAt, url}]."""
    _log(f"github.search_issues({query!r}, repo={repo!r}, limit={limit}) called")
    args = ["issue", "list", "--search", query, "--limit", str(limit),
            "--json", "number,title,author,state,labels,createdAt,url",
            "--state", "all"]
    if repo:
        args = ["issue", "list", "--repo", repo, "--search", query, "--limit", str(limit),
                "--json", "number,title,author,state,labels,createdAt,url",
                "--state", "all"]
    return [_normalize_item(i) for i in _gh_json(*args)]


def get_issue(repo: str, number: int) -> dict:
    """Get issue details. Returns {number, title, body, author, state, labels, comments, url}."""
    _log(f"github.get_issue({repo!r}, {number}) called")
    issue = _gh_json("issue", "view", str(number), "--repo", repo,
                     "--json", "number,title,body,author,state,labels,comments,url")
    # Normalize comments to clean dicts
    if "comments" in issue:
        issue["comments"] = [
            {"author": c.get("author", {}).get("login", ""), "body": c.get("body", ""), "createdAt": c.get("createdAt", "")}
            for c in issue["comments"]
        ]
    return _normalize_item(issue)


# --- Pull Requests ---

def list_prs(repo: str, state: str = "open", limit: int = 20) -> list[dict]:
    """List PRs. Returns [{number, title, author, state, headRefName, createdAt, url}]."""
    _log(f"github.list_prs({repo!r}, state={state!r}, limit={limit}) called")
    return [_normalize_item(p) for p in _gh_json(
        "pr", "list", "--repo", repo, "--state", state, "--limit", str(limit),
        "--json", "number,title,author,state,headRefName,createdAt,url",
    )]


def get_pr(repo: str, number: int) -> dict:
    """Get PR details. Returns {number, title, body, author, state, headRefName, additions, deletions, files, reviews, url}."""
    _log(f"github.get_pr({repo!r}, {number}) called")
    pr = _gh_json("pr", "view", str(number), "--repo", repo,
                  "--json", "number,title,body,author,state,headRefName,additions,deletions,files,reviews,url")
    # Normalize files to just names + changes
    if "files" in pr:
        pr["files"] = [
            {"path": f.get("path", ""), "additions": f.get("additions", 0), "deletions": f.get("deletions", 0)}
            for f in pr["files"]
        ]
    if "reviews" in pr:
        pr["reviews"] = [
            {"author": r.get("author", {}).get("login", ""), "state": r.get("state", ""), "body": r.get("body", "")}
            for r in pr["reviews"]
        ]
    return _normalize_item(pr)


# --- Commits ---

def list_commits(repo: str, branch: str = "main", limit: int = 10) -> list[dict]:
    """List recent commits. Returns [{oid, messageHeadline, author, committedDate}]."""
    _log(f"github.list_commits({repo!r}, branch={branch!r}, limit={limit}) called")
    raw = _gh("api", f"repos/{repo}/commits",
              "--jq", json.dumps([
                  f".[:{ limit}][] | {{oid: .sha, messageHeadline: .commit.message | split(\"\\n\")[0], "
                  f"author: .commit.author.name, committedDate: .commit.author.date}}"
              ][0]),
              "-q", f"sha={branch}")
    if not raw:
        return []
    # gh api --jq returns newline-separated JSON objects
    return [json.loads(line) for line in raw.strip().split("\n") if line.strip()]


# --- CI / Workflow Runs ---

def list_runs(repo: str, limit: int = 5) -> list[dict]:
    """List recent workflow runs. Returns [{id, name, status, conclusion, headBranch, createdAt, url}]."""
    _log(f"github.list_runs({repo!r}, limit={limit}) called")
    data = _gh_json("api", f"repos/{repo}/actions/runs",
                    "--jq", f"[.workflow_runs[:{ limit}][] | {{id: .id, name: .name, status: .status, conclusion: .conclusion, headBranch: .head_branch, createdAt: .created_at, url: .html_url}}]")
    return data


def get_checks(repo: str, pr_number: int) -> list[dict]:
    """Get check runs for a PR. Returns [{name, status, conclusion}]."""
    _log(f"github.get_checks({repo!r}, pr_number={pr_number}) called")
    return _gh_json("pr", "checks", str(pr_number), "--repo", repo,
                    "--json", "name,state,description",
                    "--required")
