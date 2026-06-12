import os
import subprocess
from datetime import datetime

def get_current_actor() -> str:
    """
    Resolve the current actor identity.
    Precedence: BEADS_ACTOR -> git user.name -> USER -> USERNAME -> 'agent'
    """
    actor = os.environ.get("BEADS_ACTOR")
    if actor:
        return actor.strip()
        
    try:
        git_name = subprocess.check_output(
            ["git", "config", "user.name"], stderr=subprocess.DEVNULL
        ).decode().strip()
        if git_name:
            return git_name
    except Exception:
        pass
        
    for env_var in ["USER", "USERNAME"]:
        val = os.environ.get(env_var)
        if val:
            return val.strip()
            
    return "agent"

def format_priority(priority: int) -> str:
    """Format priority integer to a human-readable tag."""
    mapping = {
        0: "Critical",
        1: "High",
        2: "Medium",
        3: "Low",
        4: "Backlog"
    }
    return mapping.get(priority, f"P{priority}")

def format_status(status: str) -> str:
    """Format status string to a display-friendly tag."""
    mapping = {
        "todo": "Todo",
        "reopened": "Reopened",
        "in_progress": "In Progress",
        "review": "Review",
        "done": "Completed"
    }
    return mapping.get(status.lower(), status.capitalize())

def format_datetime(dt: datetime) -> str:
    """Format datetime for clean console output."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")
