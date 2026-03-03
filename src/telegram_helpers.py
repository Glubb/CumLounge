"""Helper functions for telegram.py to reduce code duplication."""
import logging
from typing import Optional, Callable
from functools import wraps

import src.core as core
import src.replies as rp


def send_reply(bot, chat_id: int, reply: rp.Reply, reply_to_message_id: Optional[int] = None):
    """
    Send a formatted reply to a user.
    
    Args:
        bot: Telegram bot instance
        chat_id: Chat ID to send to
        reply: Reply object to format and send
        reply_to_message_id: Optional message ID to reply to
    """
    try:
        txt = rp.formatForTelegram(reply)
        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=reply_to_message_id)
    except Exception as e:
        logging.debug('Failed to send reply to %s: %s', chat_id, e)


def send_error(bot, chat_id: int, error_type: int, reply_to_message_id: Optional[int] = None):
    """
    Send an error message to a user.
    
    Args:
        bot: Telegram bot instance
        chat_id: Chat ID to send to
        error_type: Error type from rp.types
        reply_to_message_id: Optional message ID to reply to
    """
    send_reply(bot, chat_id, rp.Reply(error_type), reply_to_message_id)


def get_target_msid(ch, db, message, chat_id: int, bot_id: Optional[int] = None) -> Optional[int]:
    """
    Extract target msid from a replied-to message.
    
    Args:
        ch: Cache instance
        db: Database instance
        message: Telegram message object
        chat_id: User's chat ID
        bot_id: Bot ID for cross-process lookups
        
    Returns:
        Message ID (msid) or None if not found
    """
    replied = getattr(message, 'reply_to_message', None)
    if replied is None:
        return None
    
    replied_msg_id = getattr(replied, 'message_id', None)
    if not replied_msg_id:
        return None
    
    # Try cache first (O(1))
    target_msid = ch.lookupMappingByData(replied_msg_id, uid=chat_id)
    if target_msid is not None:
        return target_msid
    
    # Fallback to DB for cross-process support
    try:
        target_msid = db.get_msid_by_uid_message(chat_id, replied_msg_id, bot_id=bot_id)
        return target_msid
    except Exception as e:
        logging.debug("Failed to get msid from DB: %s", e)
        return None


def require_user(bot, db, chat_id: int) -> Optional[object]:
    """
    Get user from database, return None if not found.
    
    Args:
        bot: Telegram bot instance
        db: Database instance
        chat_id: User's chat ID
        
    Returns:
        User object or None
    """
    try:
        return db.getUser(id=chat_id)
    except KeyError:
        return None


def require_rank(bot, user, required_rank: int, message_id: Optional[int] = None) -> bool:
    """
    Check if user has required rank, send error if not.
    
    Args:
        bot: Telegram bot instance
        user: User object
        required_rank: Required rank level
        message_id: Optional message ID to reply to
        
    Returns:
        True if user has required rank, False otherwise
    """
    if user.rank < required_rank:
        send_error(bot, user.id, rp.types.ERR_COMMAND_DISABLED, message_id)
        return False
    return True


def require_reply(bot, message, chat_id: int) -> bool:
    """
    Check if message is a reply, send error if not.
    
    Args:
        bot: Telegram bot instance
        message: Telegram message object
        chat_id: User's chat ID
        
    Returns:
        True if message is a reply, False otherwise
    """
    if not getattr(message, 'reply_to_message', None):
        send_error(bot, chat_id, rp.types.ERR_NO_REPLY, getattr(message, 'message_id', None))
        return False
    return True


def extract_command_arg(text: str, required: bool = False) -> Optional[str]:
    """
    Extract argument from command text.
    
    Args:
        text: Command text (e.g., "/command arg1 arg2")
        required: Whether argument is required
        
    Returns:
        Argument string or None
    """
    parts = text.strip().split(None, 1)
    if len(parts) < 2:
        return None
    return parts[1].strip() if parts[1].strip() else None


class CommandHandler:
    """Base class for command handlers with common functionality."""
    
    def __init__(self, bot, db, ch, bot_id=None):
        self.bot = bot
        self.db = db
        self.ch = ch
        self.bot_id = bot_id
    
    def get_user(self, chat_id: int):
        """Get user or return None."""
        return require_user(self.bot, self.db, chat_id)
    
    def check_rank(self, user, required_rank: int, message_id: Optional[int] = None) -> bool:
        """Check rank and send error if insufficient."""
        return require_rank(self.bot, user, required_rank, message_id)
    
    def check_reply(self, message, chat_id: int) -> bool:
        """Check if message is a reply and send error if not."""
        return require_reply(self.bot, message, chat_id)
    
    def get_msid(self, message, chat_id: int) -> Optional[int]:
        """Get target msid from replied message."""
        return get_target_msid(self.ch, self.db, message, chat_id, self.bot_id)
    
    def send_reply(self, chat_id: int, reply: rp.Reply, reply_to: Optional[int] = None):
        """Send formatted reply."""
        send_reply(self.bot, chat_id, reply, reply_to)
    
    def send_error(self, chat_id: int, error_type: int, reply_to: Optional[int] = None):
        """Send error message."""
        send_error(self.bot, chat_id, error_type, reply_to)
