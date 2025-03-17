#!/usr/bin/env python3
"""
DevAssist Extension: Slack
Fetches messages, mentions, and activity from Slack.
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import requests

logger = logging.getLogger("devassist.extensions.slack")

# Global config
_config = {}
_session = None

def initialize(config: Dict[str, Any]):
    """Initialize the extension with the given configuration"""
    global _config, _session
    _config = config
    
    token = _config.get("token")
    if not token:
        logger.warning("Slack token not configured")
        return
    
    # Setup session with authentication
    _session = requests.Session()
    _session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    })
    
    logger.info("Slack extension initialized")

def collect_data() -> Dict[str, Any]:
    """Collect data from Slack"""
    if not _session:
        return {"error": "Slack extension not properly initialized"}
    
    result = {
        "mentions": [],
        "direct_messages": [],
        "unread_channels": [],
        "important_messages": []
    }
    
    # Get user ID first
    user_id = get_user_id()
    if not user_id:
        logger.error("Could not get Slack user ID")
        return {"error": "Could not get Slack user ID"}
    
    # Get channels to monitor
    channels = _config.get("channels", [])
    
    # Get conversations list (channels, DMs, groups)
    conversations = get_conversations(user_id)
    if not conversations:
        logger.warning("No conversations found")
    
    # Process each conversation
    for conversation in conversations:
        channel_id = conversation["id"]
        channel_name = conversation.get("name", "DM")
        
        # Skip channels not in the configured list unless it's a DM
        if channels and channel_name not in channels and not conversation.get("is_im"):
            continue
        
        # Check for unread messages
        if conversation.get("unread_count", 0) > 0:
            result["unread_channels"].append({
                "id": channel_id,
                "name": channel_name,
                "unread_count": conversation.get("unread_count", 0),
                "type": get_channel_type(conversation),
                "url": get_channel_url(channel_id)
            })
        
        # Get recent messages
        messages = get_channel_history(channel_id)
        
        # Process messages
        for message in messages:
            # Skip bot messages and system messages
            if message.get("subtype") in ["bot_message", "channel_join", "channel_leave"]:
                continue
                
            # Check if message mentions the user
            if f"<@{user_id}>" in message.get("text", ""):
                result["mentions"].append(format_message(message, channel_id, channel_name))
            
            # Add direct messages
            if conversation.get("is_im"):
                result["direct_messages"].append(format_message(message, channel_id, channel_name))
            
            # Check for important messages (has reactions or keywords)
            if is_important_message(message, user_id):
                result["important_messages"].append(format_message(message, channel_id, channel_name))
    
    return result

def get_user_id() -> Optional[str]:
    """Get the user's Slack ID"""
    try:
        response = _session.get("https://slack.com/api/auth.test")
        response.raise_for_status()
        
        data = response.json()
        if data.get("ok"):
            return data.get("user_id")
        else:
            logger.error(f"Slack API error: {data.get('error')}")
            return None
    except Exception as e:
        logger.error(f"Error getting user ID: {e}")
        return None

def get_conversations(user_id: str) -> List[Dict[str, Any]]:
    """Get list of channels, groups, and DMs"""
    try:
        params = {
            "types": "public_channel,private_channel,mpim,im",
            "exclude_archived": "true",
            "limit": 100
        }
        
        response = _session.get("https://slack.com/api/conversations.list", params=params)
        response.raise_for_status()
        
        data = response.json()
        if data.get("ok"):
            return data.get("channels", [])
        else:
            logger.error(f"Slack API error: {data.get('error')}")
            return []
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return []

def get_channel_history(channel_id: str) -> List[Dict[str, Any]]:
    """Get recent messages from a channel"""
    try:
        # Get messages from the last 24 hours
        oldest = time.time() - 86400  # 24 hours ago
        
        params = {
            "channel": channel_id,
            "limit": 50,
            "oldest": str(oldest)
        }
        
        response = _session.get("https://slack.com/api/conversations.history", params=params)
        response.raise_for_status()
        
        data = response.json()
        if data.get("ok"):
            return data.get("messages", [])
        else:
            logger.error(f"Slack API error: {data.get('error')}")
            return []
    except Exception as e:
        logger.error(f"Error getting channel history: {e}")
        return []

def is_important_message(message: Dict[str, Any], user_id: str) -> bool:
    """Determine if a message is important based on various criteria"""
    # Has reactions
    if message.get("reactions") and len(message.get("reactions", [])) > 0:
        return True
    
    # Marked as important by certain reactions
    for reaction in message.get("reactions", []):
        if reaction.get("name") in ["important", "alert", "warning", "fire", "exclamation"]:
            return True
    
    # Contains urgent keywords
    text = message.get("text", "").lower()
    urgent_keywords = ["urgent", "asap", "important", "critical", "deadline", "help", "broken", "failed", "error"]
    
    for keyword in urgent_keywords:
        if keyword in text:
            return True
    
    # Message is a reply in a thread
    if message.get("thread_ts") and message.get("reply_count", 0) > 0:
        return True
    
    # Message is from a team lead or manager (would need to configure these)
    managers = _config.get("managers", [])
    if message.get("user") in managers:
        return True
    
    return False

def format_message(message: Dict[str, Any], channel_id: str, channel_name: str) -> Dict[str, Any]:
    """Format Slack message into a simplified structure"""
    ts = message.get("ts", "0")
    thread_ts = message.get("thread_ts")
    
    formatted = {
        "id": ts,
        "channel_id": channel_id,
        "channel_name": channel_name,
        "user": message.get("user"),
        "text": message.get("text", ""),
        "timestamp": ts,
        "time": datetime.fromtimestamp(float(ts)).isoformat(),
        "has_attachments": len(message.get("attachments", [])) > 0,
        "reaction_count": sum(reaction.get("count", 0) for reaction in message.get("reactions", [])),
        "url": get_message_url(channel_id, ts)
    }
    
    # Add thread info if available
    if thread_ts:
        formatted["is_thread"] = True
        formatted["thread_id"] = thread_ts
        formatted["reply_count"] = message.get("reply_count", 0)
        formatted["thread_url"] = get_message_url(channel_id, thread_ts)
    else:
        formatted["is_thread"] = False
    
    return formatted

def get_channel_type(conversation: Dict[str, Any]) -> str:
    """Get the type of channel"""
    if conversation.get("is_im"):
        return "direct_message"
    elif conversation.get("is_mpim"):
        return "group_message"
    elif conversation.get("is_private"):
        return "private_channel"
    else:
        return "public_channel"

def get_channel_url(channel_id: str) -> str:
    """Get the URL for a channel"""
    team_id = _config.get("team_id", "T0123456789")
    return f"https://slack.com/app_redirect?channel={channel_id}&team={team_id}"

def get_message_url(channel_id: str, timestamp: str) -> str:
    """Get the URL for a message"""
    team_id = _config.get("team_id", "T0123456789")
    # Replace dots with underscores in the timestamp
    ts = timestamp.replace(".", "")
    return f"https://slack.com/app_redirect?channel={channel_id}&message_ts={timestamp}&team={team_id}"

def get_user_info(user_id: str) -> Dict[str, Any]:
    """Get information about a user"""
    try:
        params = {
            "user": user_id
        }
        
        response = _session.get("https://slack.com/api/users.info", params=params)
        response.raise_for_status()
        
        data = response.json()
        if data.get("ok"):
            user = data.get("user", {})
            return {
                "id": user.get("id"),
                "name": user.get("name"),
                "real_name": user.get("real_name"),
                "display_name": user.get("profile", {}).get("display_name"),
                "email": user.get("profile", {}).get("email"),
                "status_text": user.get("profile", {}).get("status_text"),
                "status_emoji": user.get("profile", {}).get("status_emoji")
            }
        else:
            logger.error(f"Slack API error: {data.get('error')}")
            return {}
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return {}

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
            "token": "xoxp-...",
            "team_id": "T0123456789",
            "channels": ["general", "random"],
            "managers": []
        }
    
    initialize(config)
    data = collect_data()
    print(json.dumps(data, indent=2))