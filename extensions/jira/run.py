#!/usr/bin/env python3
"""
DevAssist Extension: Jira
Fetches issues, sprints, and boards from Jira.
"""

import logging
import json
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import requests

logger = logging.getLogger("devassist.extensions.jira")

# Global config
_config = {}
_session = None

def initialize(config: Dict[str, Any]):
    """Initialize the extension with the given configuration"""
    global _config, _session
    _config = config
    
    url = _config.get("url")
    username = _config.get("username")
    api_token = _config.get("api_token")
    
    if not all([url, username, api_token]):
        logger.warning("Jira configuration incomplete")
        return
    
    # Setup session with authentication
    _session = requests.Session()
    auth = base64.b64encode(f"{username}:{api_token}".encode()).decode()
    _session.headers.update({
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    })
    
    logger.info("Jira extension initialized")

def collect_data() -> Dict[str, Any]:
    """Collect data from Jira"""
    if not _session:
        return {"error": "Jira extension not properly initialized"}
    
    result = {
        "assigned_issues": [],
        "watching_issues": [],
        "sprint_issues": [],
        "recent_activity": []
    }
    
    jira_url = _config.get("url", "").rstrip("/")
    username = _config.get("username")
    projects = _config.get("projects", [])
    
    # Get issues assigned to the user
    assigned_issues = get_assigned_issues(jira_url, username)
    if assigned_issues:
        result["assigned_issues"] = assigned_issues
    
    # Get issues the user is watching
    watching_issues = get_watching_issues(jira_url, username)
    if watching_issues:
        result["watching_issues"] = watching_issues
    
    # Get active sprint issues for each project
    for project in projects:
        sprint_issues = get_sprint_issues(jira_url, project)
        if sprint_issues:
            result["sprint_issues"].extend(sprint_issues)
    
    # Get recent activity
    activity = get_recent_activity(jira_url, username)
    if activity:
        result["recent_activity"] = activity
    
    return result

def get_assigned_issues(jira_url: str, username: str) -> List[Dict[str, Any]]:
    """Get issues assigned to the user"""
    try:
        jql = f"assignee = '{username}' AND resolution = Unresolved ORDER BY priority DESC, updated DESC"
        url = f"{jira_url}/rest/api/2/search"
        response = _session.get(url, params={"jql": jql, "maxResults": 50})
        response.raise_for_status()
        
        data = response.json()
        return [format_issue(issue) for issue in data.get("issues", [])]
    except Exception as e:
        logger.error(f"Error fetching assigned issues: {e}")
        return []

def get_watching_issues(jira_url: str, username: str) -> List[Dict[str, Any]]:
    """Get issues the user is watching"""
    try:
        jql = f"watcher = '{username}' AND resolution = Unresolved ORDER BY updated DESC"
        url = f"{jira_url}/rest/api/2/search"
        response = _session.get(url, params={"jql": jql, "maxResults": 20})
        response.raise_for_status()
        
        data = response.json()
        return [format_issue(issue) for issue in data.get("issues", [])]
    except Exception as e:
        logger.error(f"Error fetching watching issues: {e}")
        return []

def get_sprint_issues(jira_url: str, project: str) -> List[Dict[str, Any]]:
    """Get active sprint issues for a project"""
    try:
        # First, get the board ID for the project
        url = f"{jira_url}/rest/agile/1.0/board"
        response = _session.get(url, params={"projectKeyOrId": project})
        response.raise_for_status()
        
        boards = response.json().get("values", [])
        if not boards:
            logger.warning(f"No boards found for project {project}")
            return []
        
        board_id = boards[0]["id"]
        
        # Get active sprints for the board
        url = f"{jira_url}/rest/agile/1.0/board/{board_id}/sprint"
        response = _session.get(url, params={"state": "active"})
        response.raise_for_status()
        
        sprints = response.json().get("values", [])
        if not sprints:
            logger.warning(f"No active sprints found for board {board_id}")
            return []
        
        sprint_id = sprints[0]["id"]
        
        # Get issues for the active sprint
        url = f"{jira_url}/rest/agile/1.0/sprint/{sprint_id}/issue"
        response = _session.get(url, params={"maxResults": 100})
        response.raise_for_status()
        
        data = response.json()
        sprint_name = sprints[0]["name"]
        issues = [
            {**format_issue(issue), "sprint": sprint_name}
            for issue in data.get("issues", [])
        ]
        
        return issues
    except Exception as e:
        logger.error(f"Error fetching sprint issues for project {project}: {e}")
        return []

def get_recent_activity(jira_url: str, username: str) -> List[Dict[str, Any]]:
    """Get recent activity related to the user"""
    try:
        # Use the activity stream to get recent updates
        # This endpoint might vary depending on Jira version/deployment
        url = f"{jira_url}/activity"
        params = {
            "streams": "user IS {0}".format(username),
            "maxResults": 20
        }
        
        response = _session.get(url, params=params)
        response.raise_for_status()
        
        # Activity stream returns complex XML/JSON data
        # Simplified approach: get recently updated issues instead
        jql = f"updatedBy = '{username}' OR commentedBy = '{username}' ORDER BY updated DESC"
        url = f"{jira_url}/rest/api/2/search"
        response = _session.get(url, params={"jql": jql, "maxResults": 10})
        response.raise_for_status()
        
        data = response.json()
        return [
            {
                "id": issue["id"],
                "key": issue["key"],
                "summary": issue["fields"]["summary"],
                "updated": issue["fields"]["updated"],
                "type": "issue_update",
                "url": f"{jira_url}/browse/{issue['key']}"
            }
            for issue in data.get("issues", [])
        ]
    except Exception as e:
        logger.error(f"Error fetching recent activity: {e}")
        return []

def format_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Format issue data into a simplified structure"""
    fields = issue.get("fields", {})
    
    # Extract assignee info safely
    assignee = fields.get("assignee") or {}
    assignee_name = assignee.get("displayName", "Unassigned")
    
    # Extract status info safely
    status = fields.get("status") or {}
    status_name = status.get("name", "Unknown")
    
    # Extract priority info safely
    priority = fields.get("priority") or {}
    priority_name = priority.get("name", "None")
    
    result = {
        "id": issue.get("id"),
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "description": fields.get("description"),
        "status": status_name,
        "priority": priority_name,
        "assignee": assignee_name,
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "due_date": fields.get("duedate"),
        "url": f"{_config.get('url', '').rstrip('/')}/browse/{issue.get('key')}"
    }
    
    # Add issue type
    issue_type = fields.get("issuetype") or {}
    result["issue_type"] = issue_type.get("name", "Unknown")
    
    # Add labels
    result["labels"] = fields.get("labels", [])
    
    # Add epic link if available
    epic_link = fields.get("customfield_10014")  # Common epic link field, may vary
    if epic_link:
        result["epic"] = epic_link
    
    # Add story points if available
    story_points = fields.get("customfield_10002")  # Common story points field, may vary
    if story_points:
        result["story_points"] = story_points
    
    return result

def get_user_worklog(jira_url: str, username: str, days: int = 7) -> List[Dict[str, Any]]:
    """Get the user's recent worklog entries"""
    try:
        # Calculate date from N days ago
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # JQL to find issues with worklog by the user since the date
        jql = f"worklogAuthor = '{username}' AND worklogDate >= '{since}' ORDER BY updated DESC"
        url = f"{jira_url}/rest/api/2/search"
        response = _session.get(url, params={"jql": jql, "maxResults": 50})
        response.raise_for_status()
        
        data = response.json()
        issues = data.get("issues", [])
        
        worklog_entries = []
        for issue in issues:
            issue_key = issue.get("key")
            issue_summary = issue.get("fields", {}).get("summary", "")
            
            # Get worklog for this issue
            worklog_url = f"{jira_url}/rest/api/2/issue/{issue_key}/worklog"
            worklog_response = _session.get(worklog_url)
            worklog_response.raise_for_status()
            
            worklog_data = worklog_response.json()
            
            for entry in worklog_data.get("worklogs", []):
                author = entry.get("author", {}).get("name", "")
                
                if author == username and entry.get("started", "").startswith(since):
                    worklog_entries.append({
                        "issue_key": issue_key,
                        "issue_summary": issue_summary,
                        "author": author,
                        "time_spent": entry.get("timeSpent"),
                        "time_spent_seconds": entry.get("timeSpentSeconds"),
                        "comment": entry.get("comment"),
                        "started": entry.get("started"),
                        "url": f"{jira_url}/browse/{issue_key}"
                    })
        
        return worklog_entries
    except Exception as e:
        logger.error(f"Error fetching user worklog: {e}")
        return []

def get_project_stats(jira_url: str, project: str) -> Dict[str, Any]:
    """Get statistics for a project"""
    try:
        result = {
            "project": project,
            "total_issues": 0,
            "open_issues": 0,
            "in_progress": 0,
            "resolved": 0,
            "closed": 0
        }
        
        # Get total issues count
        jql = f"project = '{project}'"
        url = f"{jira_url}/rest/api/2/search"
        response = _session.get(url, params={"jql": jql, "maxResults": 0})
        response.raise_for_status()
        
        result["total_issues"] = response.json().get("total", 0)
        
        # Get open issues count
        jql = f"project = '{project}' AND resolution = Unresolved"
        response = _session.get(url, params={"jql": jql, "maxResults": 0})
        response.raise_for_status()
        
        result["open_issues"] = response.json().get("total", 0)
        
        # Get in-progress issues count
        jql = f"project = '{project}' AND status = 'In Progress'"
        response = _session.get(url, params={"jql": jql, "maxResults": 0})
        response.raise_for_status()
        
        result["in_progress"] = response.json().get("total", 0)
        
        # Get resolved issues count
        jql = f"project = '{project}' AND resolution = Resolved"
        response = _session.get(url, params={"jql": jql, "maxResults": 0})
        response.raise_for_status()
        
        result["resolved"] = response.json().get("total", 0)
        
        # Get closed issues count
        jql = f"project = '{project}' AND status = Closed"
        response = _session.get(url, params={"jql": jql, "maxResults": 0})
        response.raise_for_status()
        
        result["closed"] = response.json().get("total", 0)
        
        return result
    except Exception as e:
        logger.error(f"Error fetching project stats for {project}: {e}")
        return {"project": project, "error": str(e)}

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
            "url": "https://your-jira-instance.atlassian.net",
            "username": "your-email@example.com",
            "api_token": "your-api-token",
            "projects": ["PROJECT"]
        }
    
    initialize(config)
    data = collect_data()
    print(json.dumps(data, indent=2))