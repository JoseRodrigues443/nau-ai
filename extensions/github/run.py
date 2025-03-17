#!/usr/bin/env python3
"""
DevAssist Extension: GitHub
Fetches pull requests, issues, and notifications from GitHub.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import requests

logger = logging.getLogger("devassist.extensions.github")

# GitHub API URLs
API_BASE = "https://api.github.com"
PR_ENDPOINT = "/repos/{owner}/{repo}/pulls"
ISSUES_ENDPOINT = "/repos/{owner}/{repo}/issues"
NOTIFICATIONS_ENDPOINT = "/notifications"

# Global config
_config = {}
_session = None

def initialize(config: Dict[str, Any]):
    """Initialize the extension with the given configuration"""
    global _config, _session
    _config = config
    
    token = _config.get("token")
    if not token:
        logger.warning("GitHub token not configured")
        return
    
    # Setup session with authentication
    _session = requests.Session()
    _session.headers.update({
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "DevAssist-GitHub-Extension"
    })
    
    logger.info("GitHub extension initialized")

def collect_data() -> Dict[str, Any]:
    """Collect data from GitHub"""
    if not _session:
        return {"error": "GitHub extension not properly initialized"}
    
    result = {
        "pull_requests": [],
        "issues": [],
        "notifications": []
    }
    
    repositories = _config.get("repositories", [])
    if not repositories:
        logger.warning("No repositories configured")
    
    # Collect pull requests and issues for each repository
    for repo in repositories:
        try:
            owner, repo_name = repo.split("/")
            
            # Get pull requests
            prs = get_pull_requests(owner, repo_name)
            if prs:
                for pr in prs:
                    result["pull_requests"].append({
                        "repo": repo,
                        "id": pr["number"],
                        "title": pr["title"],
                        "url": pr["html_url"],
                        "created_at": pr["created_at"],
                        "updated_at": pr["updated_at"],
                        "user": pr["user"]["login"],
                        "state": pr["state"],
                        "reviews": get_pr_reviews(owner, repo_name, pr["number"]),
                        "is_draft": pr.get("draft", False)
                    })
            
            # Get issues
            issues = get_issues(owner, repo_name)
            if issues:
                for issue in issues:
                    # Skip pull requests (they are also returned by the issues endpoint)
                    if "pull_request" in issue:
                        continue
                    
                    result["issues"].append({
                        "repo": repo,
                        "id": issue["number"],
                        "title": issue["title"],
                        "url": issue["html_url"],
                        "created_at": issue["created_at"],
                        "updated_at": issue["updated_at"],
                        "user": issue["user"]["login"],
                        "state": issue["state"],
                        "labels": [label["name"] for label in issue["labels"]]
                    })
        except Exception as e:
            logger.error(f"Error fetching data for {repo}: {e}")
    
    # Get notifications
    notifications = get_notifications()
    if notifications:
        for notification in notifications:
            result["notifications"].append({
                "id": notification["id"],
                "repo": notification["repository"]["full_name"],
                "subject": notification["subject"]["title"],
                "reason": notification["reason"],
                "updated_at": notification["updated_at"],
                "url": notification["subject"]["url"],
                "type": notification["subject"]["type"]
            })
    
    return result

def get_pull_requests(owner: str, repo: str) -> List[Dict[str, Any]]:
    """Get open pull requests for a repository"""
    try:
        url = f"{API_BASE}{PR_ENDPOINT.format(owner=owner, repo=repo)}"
        response = _session.get(url, params={"state": "open"})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching pull requests for {owner}/{repo}: {e}")
        return []

def get_pr_reviews(owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
    """Get reviews for a pull request"""
    try:
        url = f"{API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        response = _session.get(url)
        response.raise_for_status()
        
        reviews = response.json()
        # Simplify the reviews data
        return [
            {
                "user": review["user"]["login"],
                "state": review["state"],
                "submitted_at": review["submitted_at"]
            }
            for review in reviews
        ]
    except Exception as e:
        logger.error(f"Error fetching reviews for PR #{pr_number} in {owner}/{repo}: {e}")
        return []

def get_issues(owner: str, repo: str) -> List[Dict[str, Any]]:
    """Get open issues for a repository"""
    try:
        url = f"{API_BASE}{ISSUES_ENDPOINT.format(owner=owner, repo=repo)}"
        response = _session.get(url, params={"state": "open"})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching issues for {owner}/{repo}: {e}")
        return []

def get_notifications() -> List[Dict[str, Any]]:
    """Get recent notifications"""
    try:
        # Get notifications from the last 7 days
        since = (datetime.now() - timedelta(days=7)).isoformat()
        url = f"{API_BASE}{NOTIFICATIONS_ENDPOINT}"
        response = _session.get(url, params={"all": "false", "since": since})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        return []

if __name__ == "__main__":
    # For testing the extension directly
    import sys
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Load config from command line or use default
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {
            "token": "",
            "repositories": ["owner/repo"]
        }
    
    initialize(config)
    data = collect_data()
    print(json.dumps(data, indent=2))