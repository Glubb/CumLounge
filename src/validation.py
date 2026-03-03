"""Input validation and sanitization utilities."""
import re
import unicodedata
from typing import Optional


def sanitize_text(text: Optional[str], max_length: int = 500) -> Optional[str]:
    """
    Sanitize user input text.
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text or None if invalid
    """
    if not text or not isinstance(text, str):
        return None
    
    text = text.strip()
    if not text:
        return None
        
    if len(text) > max_length:
        text = text[:max_length]
    
    # Remove control characters except newlines and tabs
    text = ''.join(
        c for c in text 
        if c in ('\n', '\t') or not unicodedata.category(c).startswith('C')
    )
    
    return text.strip() if text.strip() else None


def sanitize_username(username: Optional[str]) -> Optional[str]:
    """
    Sanitize username input.
    
    Args:
        username: Username to sanitize
        
    Returns:
        Sanitized username or None if invalid
    """
    if not username or not isinstance(username, str):
        return None
    
    username = username.strip().lstrip('@')
    
    # Telegram usernames: 5-32 chars, alphanumeric + underscore
    if not re.match(r'^[a-zA-Z0-9_]{1,32}$', username):
        return None
    
    return username.lower()


def validate_duration_string(duration: str) -> bool:
    """
    Validate duration string format (e.g., "1h 30m", "2d").
    
    Args:
        duration: Duration string to validate
        
    Returns:
        True if valid format
    """
    if not duration or not isinstance(duration, str):
        return False
    
    # Pattern: number followed by unit (s/m/h/d/w)
    pattern = r'^\s*(\d+\s*[smhdw]\s*)+$'
    return bool(re.match(pattern, duration.lower()))


def validate_config(config: dict) -> list[str]:
    """
    Validate configuration dictionary.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    # Required fields
    if not config.get("bot_token"):
        errors.append("bot_token is required")
    
    # Validate numeric fields
    numeric_fields = {
        "karma_amount_add": (1, 100),
        "karma_amount_remove": (1, 100),
        "sign_limit_interval": (0, 86400),
        "vote_up_limit_interval": (0, 3600),
        "vote_down_limit_interval": (0, 3600),
        "media_auto_disable_hours": (0, 168),
    }
    
    for field, (min_val, max_val) in numeric_fields.items():
        value = config.get(field)
        if value is not None:
            if not isinstance(value, (int, float)):
                errors.append(f"{field} must be a number")
            elif value < min_val or value > max_val:
                errors.append(f"{field} must be between {min_val} and {max_val}")
    
    # Validate database config
    db_config = config.get("database")
    if db_config:
        if not isinstance(db_config, list) or len(db_config) != 2:
            errors.append("database must be [type, path]")
        elif db_config[0] not in ("json", "sqlite"):
            errors.append("database type must be 'json' or 'sqlite'")
    
    # Validate boolean fields
    bool_fields = [
        "reg_open", "allow_contacts", "allow_documents", 
        "allow_polls", "enable_signing", "karma_is_pats",
        "media_blocked", "is_leader"
    ]
    
    for field in bool_fields:
        value = config.get(field)
        if value is not None and not isinstance(value, bool):
            errors.append(f"{field} must be a boolean")
    
    return errors
