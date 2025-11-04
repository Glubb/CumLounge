import logging
import time
import json
import telebot
from telebot.types import ReactionTypeEmoji
import datetime

import src.core as core
import src.replies as rp
from src.cache import CachedMessage
from src.util import MutablePriorityQueue
from src.globals import SCORE_BASE_MESSAGE, SCORE_TEXT_CHARACTER, SCORE_TEXT_LINEBREAK

# Globals initialized in init()
bot = None
db = None
ch = None
message_queue = None
BOT_ID = None
BOT_USERNAME = None
GLOBAL_COUNT_LABEL = "Global user count"

# Cache for reachable user IDs to reduce DB queries
_reachable_cache = None
_cache_time = None

# Config flags
allow_contacts = False
allow_documents = False
allow_polls = False


# Minimal Receiver to deliver system messages emitted by core
class _TelegramReceiver(core.Receiver):
    @staticmethod
    def reply(m, msid, who, except_who, reply_to):
        text = rp.formatForTelegram(m)
        _uid = lambda x: x.id if hasattr(x, 'id') else int(x) if x is not None else None

        # Determine recipients
        recipients = []
        if who is None:
            reachable_ids = _get_cached_reachable_ids()
            
            for u in db.iterateUsers():
                if not u.isJoined() or u.isBlacklisted():
                    continue
                if except_who is not None and _uid(except_who) == u.id:
                    continue
                if BOT_ID is not None and u.id not in reachable_ids:
                    continue
                recipients.append(u.id)
        else:
            uid = _uid(who)
            if uid is not None:
                recipients.append(uid)

        # Send to recipients, optionally as a reply to a mapped message
        for rid in recipients:
            kwargs = {"parse_mode": "HTML"}
            try:
                if reply_to is not None:
                    msg_id = ch.lookupMapping(rid, msid=reply_to)
                    if msg_id is not None:
                        kwargs["reply_to_message_id"] = msg_id
                        kwargs["allow_sending_without_reply"] = True
                bot.send_message(rid, text, **kwargs)
                logging.debug("Delivered system message to %s", rid)
            except Exception as e:
                logging.debug("Failed to deliver system message to %s: %s", rid, e)

    @staticmethod
    def delete(msids):
        pass

    @staticmethod
    def stop_invoked(who, delete_out=False):
        pass

def log_into_channel(msg, html=False):
    pass


def _get_cached_reachable_ids():
    """Get reachable user IDs with 5-second caching to reduce DB queries."""
    global _reachable_cache, _cache_time
    now = time.time()
    if _reachable_cache is None or _cache_time is None or (now - _cache_time) > 5:
        try:
            _reachable_cache = set(db.get_reachable_user_ids(BOT_ID)) if BOT_ID else set()
            _cache_time = now
        except Exception:
            _reachable_cache = set()
    return _reachable_cache


def _broadcast_targets(sender_id):
    """Yield users who should receive a forwarded copy (excludes sender and non-joined).
    Only yields users reachable by this bot token."""
    reachable_ids = _get_cached_reachable_ids()
    
    for u in db.iterateUsers():
        if u.id == sender_id or not u.isJoined() or u.isBlacklisted():
            continue
        if BOT_ID is not None and u.id not in reachable_ids:
            continue
        yield u


def send_to_single_inner(chat_id, ev, reply_to=None, force_caption=None):
    """Low-level send using the incoming Telegram message as source.
    Returns the Telegram message object."""
    kwargs = {}
    if reply_to is not None:
        kwargs["reply_to_message_id"] = reply_to
        kwargs["allow_sending_without_reply"] = True

    ct = getattr(ev, 'content_type', None)
    if ct == 'text':
        # Forward user text as plain text to avoid HTML parsing of unescaped input
        return bot.send_message(chat_id, ev.text, parse_mode=None, **kwargs)
    elif ct == 'photo' and ev.photo:
        photo = max(ev.photo, key=lambda p: p.width * p.height)
        return bot.send_photo(chat_id, photo.file_id, **kwargs)
    elif ct == 'sticker':
        return bot.send_sticker(chat_id, ev.sticker.file_id, **kwargs)
    elif ct == 'animation':
        return bot.send_animation(chat_id, ev.animation.file_id, **kwargs)
    elif ct == 'audio':
        return bot.send_audio(chat_id, ev.audio.file_id, **kwargs)
    elif ct == 'document':
        return bot.send_document(chat_id, ev.document.file_id, **kwargs)
    elif ct == 'video':
        return bot.send_video(chat_id, ev.video.file_id, **kwargs)
    elif ct == 'voice':
        return bot.send_voice(chat_id, ev.voice.file_id, **kwargs)
    elif ct == 'video_note':
        return bot.send_video_note(chat_id, ev.video_note.file_id, **kwargs)
    elif ct == 'location':
        return bot.send_location(chat_id, ev.location.latitude, ev.location.longitude, **kwargs)
    elif ct == 'contact':
        return bot.send_contact(chat_id, ev.contact.phone_number, ev.contact.first_name, **kwargs)
    else:
        # Fallback: send text as plain text (no HTML) if present
        return bot.send_message(chat_id, str(getattr(ev, 'text', '')), parse_mode=None, **kwargs)


def send_to_single(ev, msid, user, *, reply_msid=None, force_caption=None):
    """Queue a single copy for a user."""
    item = type("QueueItem", (), {
        "msid": msid,
        "msg": ev,
        "reply_msid": reply_msid,
        "user": user,
        "force_caption": force_caption,
        "timestamp": time.time()
    })
    message_queue.put(0, item)


def send_thread():
    """Background worker sending queued messages."""
    while True:
        try:
            item = message_queue.get()
            if not item:
                time.sleep(0.05)
                continue

            reply_to = None
            sent = send_to_single_inner(item.user.id, item.msg, reply_to, item.force_caption)
            if sent and hasattr(sent, 'message_id') and item.msid is not None:
                ch.saveMapping(item.user.id, item.msid, sent.message_id)
                try:
                    db.save_message_mapping(item.user.id, item.msid, sent.message_id, bot_id=BOT_ID)
                except Exception:
                    pass
        except Exception as e:
            error_msg = str(e).lower()
            if "chat not found" in error_msg or ("400" in error_msg and "not found" in error_msg):
                try:
                    if BOT_ID is not None and hasattr(item, 'user'):
                        db.set_bot_user_send_blocked(BOT_ID, item.user.id)
                        logging.debug("Marked user %s as unreachable for bot %s", item.user.id, BOT_ID)
                        global _cache_time
                        _cache_time = None  # Invalidate cache
                except Exception:
                    pass
                continue
            
            logging.warning("Message delivery failed: %s", e)
            try:
                if time.time() - getattr(item, 'timestamp', 0) < 60:
                    time.sleep(0.5)
                    message_queue.put(0, item)
            except Exception:
                time.sleep(0.5)


def relay(message):
    """Main incoming message handler: forward to all active users (except sender)."""
    sender_id = message.from_user.id if hasattr(message, 'from_user') else message.chat.id
    
    # Early exit if user not joined
    try:
        user_obj = db.getUser(id=sender_id)
        if not user_obj.isJoined():
            return
    except KeyError:
        return
    
    # Mark user as reachable and invalidate cache
    if BOT_ID is not None:
        try:
            db.mark_bot_user_seen(BOT_ID, sender_id)
            global _cache_time
            _cache_time = None
        except Exception:
            pass
    
    # Update lastActive
    try:
        with db.modifyUser(id=sender_id) as u:
            u.lastActive = datetime.datetime.now()
    except Exception as e:
        pass
    
    # Check media restrictions
    ct = getattr(message, 'content_type', '')
    is_media = ct in {'photo','animation','document','video','sticker','voice','video_note','audio','poll'}
    is_forward = bool(getattr(message, 'forward_from', None) or getattr(message, 'forward_from_chat', None))
    
    if getattr(core, 'media_blocked', False) and (is_media or is_forward):
        if not (user_obj and user_obj.rank >= core.RANKS.admin):
            txt = rp.formatForTelegram(rp.Reply(rp.types.ERR_MEDIA_DISABLED))
            bot.send_message(sender_id, txt, parse_mode='HTML', reply_to_message_id=getattr(message, 'message_id', None))
            return
    
    # Cache message and create mappings
    cm = CachedMessage(user_id=sender_id)
    msid = ch.assignMessageId(cm)
    try:
        ch.saveMapping(sender_id, msid, message.message_id)
        db.save_message_mapping(sender_id, msid, message.message_id, bot_id=BOT_ID)
    except Exception:
        pass
    
    # Broadcast to all targets
    for u in _broadcast_targets(sender_id):
        send_to_single(message, msid, u)
    
    logging.debug("relay(): msid=%d broadcast queued", msid)


def register_tasks(sched):
    def clean_expired_messages():
        try:
            expired = ch.expire()
            if not expired:
                return
            n = 0
            def selector(item):
                nonlocal n
                if item.msid in expired:
                    n += 1
                    return True
                return False
            message_queue.delete(selector)
            if n > 0:
                logging.warning("Failed to deliver %d messages before they expired from cache.", n)
        except Exception:
            logging.exception("Error in telegram cleanup task")

    sched.register(clean_expired_messages, hours=6)


def check_reaction_support():
    try:
        me = bot.get_me()
        logging.info(f"Bot initialized: @{me.username} (ID: {me.id})")
        return True
    except Exception as e:
        logging.error("Error checking bot: %s", e)
        return False


def run():
    # Include reaction updates so we can process reactions/karma
    allowed_updates = [
        "message",
        "edited_message",
        "callback_query",
        "message_reaction",
        "message_reaction_count",
    ]
    try:
        logging.debug(f"Starting bot.polling with allowed_updates={allowed_updates}")
        bot.infinity_polling(timeout=45, allowed_updates=allowed_updates, skip_pending=True)
    except Exception as e:
        logging.error("Polling error: %s", e, exc_info=True)
        time.sleep(1)


def init(config, _db, _ch):
    global bot, db, ch, message_queue, allow_contacts, allow_documents, allow_polls, GLOBAL_COUNT_LABEL

    if not config.get("bot_token"):
        logging.error("No telegram token specified.")
        raise SystemExit(1)

    telebot.apihelper.SKIP_PENDING = True
    telebot.apihelper.READ_TIMEOUT = 20

    # Save deps
    db = _db
    ch = _ch
    message_queue = MutablePriorityQueue()

    allow_contacts = bool(config.get("allow_contacts", False))
    allow_documents = bool(config.get("allow_documents", False))
    allow_polls = bool(config.get("allow_polls", False))

    bot = telebot.TeleBot(config["bot_token"], threaded=False, parse_mode="HTML")
    # Identify this bot instance for DB scoping
    try:
        me = bot.get_me()
        logging.info(f"Bot initialized: @{me.username} (ID: {me.id})")
        globals()["BOT_ID"] = int(me.id)
        globals()["BOT_USERNAME"] = str(me.username)
    except Exception as e:
        logging.warning("Could not resolve bot identity: %s", e)

    # Custom label for global user count in /users
    try:
        GLOBAL_COUNT_LABEL = str(config.get("global_user_count_label", GLOBAL_COUNT_LABEL))
    except Exception:
        pass

    # Register as a core receiver so system messages can be delivered here
    try:
        core.registerReceiver(_TelegramReceiver)
    except Exception:
        # Avoid duplicate registration on re-init
        pass

    # Register message handler for relevant content types
    types = ["text", "location", "venue"]
    if allow_contacts:
        types += ["contact"]
    if allow_documents:
        types += ["document"]
    if allow_polls:
        types += ["poll"]
    types += ["animation", "audio", "photo", "sticker", "video", "video_note", "voice"]

    def _handle_command(m) -> bool:
        try:
            text = getattr(m, 'text', '') or ''
            if not text.startswith('/'):
                return False
            cmd = text.split()[0].split('@')[0].lstrip('/')
            chat_id = m.chat.id
            
            # Handle start command
            if cmd == 'start':
                c_user = type('User', (), {
                    'id': chat_id,
                    'username': getattr(m.from_user, 'username', None),
                    'realname': ' '.join(filter(None, [
                        getattr(m.from_user, 'first_name', ''),
                        getattr(m.from_user, 'last_name', '')
                    ])) or 'Unknown'
                })()
                res = core.user_join(c_user)
                if res:
                    replies = res if isinstance(res, list) else [res]
                    for reply in replies:
                        try:
                            txt = rp.formatForTelegram(reply)
                            bot.send_message(chat_id, txt, parse_mode='HTML')
                        except Exception as e:
                            logging.debug('start reply failed: %s', e)
                return True

            # Help: show available commands
            if cmd == 'help':
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                try:
                    reply = rp.Reply(rp.types.HELP, rank=c_user.rank, karma_is_pats=core.karma_is_pats)
                    txt = rp.formatForTelegram(reply)
                    bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=getattr(m, 'message_id', None))
                except Exception:
                    pass
                return True

            # Info: show info about your account, or (mods) info about replied user
            if cmd == 'info':
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                replied = getattr(m, 'reply_to_message', None)
                res = None
                if replied is not None and c_user.rank >= core.RANKS.mod:
                    target_msid = ch.lookupMappingByData(replied.message_id, uid=chat_id) or getattr(db, 'get_msid_by_uid_message', lambda *_args, **_kw: None)(chat_id, replied.message_id, bot_id=BOT_ID)
                    if target_msid is not None:
                        res = core.get_info_mod(c_user, target_msid)
                if res is None:
                    res = core.get_info(c_user)
                if res:
                    try:
                        txt = rp.formatForTelegram(res)
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=getattr(m, 'message_id', None))
                    except Exception:
                        pass
                return True

            # Users: show user counts
            if cmd == 'users':
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                # Compute per-bot and global counts
                total_joined = 0
                reachable_ids = set()
                try:
                    if BOT_ID is not None:
                        reachable_ids = set(db.get_reachable_user_ids(BOT_ID))
                except Exception:
                    reachable_ids = set()
                per_bot_joined = 0
                for u in db.iterateUsers():
                    if u.isJoined():
                        total_joined += 1
                        if BOT_ID is None or u.id in reachable_ids:
                            per_bot_joined += 1

                # Build a compact summary and append legacy breakdown for mods/admins
                lines = [
                    f"Users in this bot: <b>{per_bot_joined}</b>",
                    f"{GLOBAL_COUNT_LABEL}: <b>{total_joined}</b>",
                ]
                try:
                    legacy = core.get_users(c_user)
                    if legacy:
                        legacy_txt = rp.formatForTelegram(legacy)
                        # Separate sections
                        lines.append("")
                        lines.append(legacy_txt)
                except Exception:
                    pass
                out = "\n".join(lines)
                try:
                    bot.send_message(chat_id, out, parse_mode='HTML', reply_to_message_id=getattr(m, 'message_id', None))
                except Exception:
                    pass
                return True

            # Remove: delete the replied message (mods)
            if cmd == 'remove':
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                if c_user.rank < core.RANKS.mod:
                    try:
                        txt = rp.formatForTelegram(rp.Reply(rp.types.ERR_COMMAND_DISABLED))
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                    return True
                replied = getattr(m, 'reply_to_message', None)
                if replied is None:
                    try:
                        txt = rp.formatForTelegram(rp.Reply(rp.types.ERR_NO_REPLY))
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                    return True
                target_msid = ch.lookupMappingByData(replied.message_id, uid=chat_id)
                if target_msid is None:
                    try:
                        target_msid = db.get_msid_by_uid_message(chat_id, replied.message_id, bot_id=BOT_ID)
                    except Exception:
                        target_msid = None
                if target_msid is None:
                    try:
                        txt = rp.formatForTelegram(rp.Reply(rp.types.ERR_NOT_IN_CACHE))
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                    return True
                res = core.delete_message(c_user, target_msid, del_all=False)
                if res:
                    try:
                        txt = rp.formatForTelegram(res)
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                return True

            # ks: sign a message with karma level
            if cmd == 'ks':
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                parts = text.strip().split(None, 1)
                if len(parts) < 2 or not parts[1].strip():
                    try:
                        txt = rp.formatForTelegram(rp.Reply(rp.types.ERR_NO_ARG))
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                    return True
                body = parts[1].strip()
                # Prepare (spam checks, cooldown, signing rules)
                score = (
                    SCORE_BASE_MESSAGE + len(body) * SCORE_TEXT_CHARACTER + body.count('\n') * SCORE_TEXT_LINEBREAK
                )
                prep = core.prepare_user_message(c_user, score, is_media=False, signed=False, tripcode=False, ksigned=True)
                # On error, core returns a Reply
                if isinstance(prep, rp.Reply):
                    try:
                        txt = rp.formatForTelegram(prep)
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                    return True
                msid = int(prep)
                # Compose signed-with-level text in plain text (no HTML)
                level_name = core.getKarmaLevelName(c_user.karma)
                out_text = f"{body}\n— {level_name}"
                # Synthetic text event
                ev = type('Ev', (), {'content_type': 'text', 'text': out_text})()
                # Broadcast to all targets (except sender)
                for u in _broadcast_targets(chat_id):
                    send_to_single(ev, msid, u)
                return True

            # Admin promotions: /mod USERNAME or /admin USERNAME (admin-only)
            if cmd in ('mod', 'admin'):
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                # Expect a username arg
                parts = text.strip().split(None, 1)
                if len(parts) < 2 or not parts[1].strip():
                    try:
                        txt = rp.formatForTelegram(rp.Reply(rp.types.ERR_NO_ARG))
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                    return True
                username = parts[1].strip()
                target_rank = core.RANKS.admin if cmd == 'admin' else core.RANKS.mod
                res = core.promote_user(c_user, username, target_rank)
                if res:
                    try:
                        txt = rp.formatForTelegram(res)
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                return True

            # Demote: /demote USERNAME (admin-only)
            if cmd == 'demote':
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                parts = text.strip().split(None, 1)
                if len(parts) < 2 or not parts[1].strip():
                    try:
                        txt = rp.formatForTelegram(rp.Reply(rp.types.ERR_NO_ARG))
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                    return True
                username = parts[1].strip()
                res = core.demote_user(c_user, username)
                if res:
                    try:
                        txt = rp.formatForTelegram(res)
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                return True
            
            # Handle stop command
            if cmd == 'stop':
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                res = core.user_leave(c_user)
                if res:
                    try:
                        txt = rp.formatForTelegram(res)
                        bot.send_message(chat_id, txt, parse_mode='HTML')
                    except Exception as e:
                        logging.debug('stop reply failed: %s', e)
                return True
            
            # Handle pin/unpin commands (mods and admins only)
            if cmd in ('pin', 'unpin'):
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                # Permission check: at least moderator
                if c_user.rank < core.RANKS.mod:
                    try:
                        txt = rp.formatForTelegram(rp.Reply(rp.types.ERR_COMMAND_DISABLED))
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                    return True

                # Determine msid either from reply or from argument
                target_msid = None
                replied = getattr(m, 'reply_to_message', None)
                if replied is not None:
                    # Prefer cache O(1) lookup
                    target_msid = ch.lookupMappingByData(replied.message_id, uid=chat_id)
                    if target_msid is None:
                        try:
                            target_msid = db.get_msid_by_uid_message(chat_id, replied.message_id, bot_id=BOT_ID)
                        except Exception:
                            target_msid = None
                else:
                    # Try parse numeric msid from command arg
                    parts = text.strip().split()
                    if len(parts) > 1 and parts[1].isdigit():
                        try:
                            target_msid = int(parts[1])
                        except Exception:
                            target_msid = None

                if target_msid is None:
                    # Inform user how to use
                    try:
                        help_txt = "Reply to a message with /pin or /unpin, or use: /pin <msid>"
                        bot.send_message(chat_id, help_txt, reply_to_message_id=getattr(m, 'message_id', None))
                    except Exception:
                        pass
                    return True

                # Gather all recipient message ids for this msid
                recipient_pairs = []  # list of (uid, message_id)
                try:
                    # First try cache for faster mapping
                    for recipient in db.iterateUsers():
                        if not recipient.isJoined():
                            continue
                        mid = ch.lookupMapping(recipient.id, msid=target_msid)
                        if mid:
                            recipient_pairs.append((recipient.id, mid))
                    if not recipient_pairs:
                        # Fallback to DB cross-process mapping
                        recipient_pairs = getattr(db, 'get_recipient_mappings_by_msid', lambda _msid, _bid=None: [])(target_msid, BOT_ID)
                except Exception:
                    pass

                if not recipient_pairs:
                    try:
                        bot.send_message(chat_id, "Couldn't find copies of that message to pin.", reply_to_message_id=m.message_id)
                    except Exception:
                        pass
                    return True

                success, failed = 0, 0
                for (rcpt_uid, rcpt_msg_id) in recipient_pairs:
                    try:
                        if cmd == 'pin':
                            bot.pin_chat_message(rcpt_uid, rcpt_msg_id)
                        else:
                            # unpin specific message
                            bot.unpin_chat_message(rcpt_uid, rcpt_msg_id)
                        success += 1
                    except Exception as e:
                        failed += 1
                        logging.debug("pin/unpin failed for uid=%s mid=%s: %s", rcpt_uid, rcpt_msg_id, e)

                # Acknowledge
                try:
                    action = 'Pinned' if cmd == 'pin' else 'Unpinned'
                    msg = f"{action} this message in {success} chats"
                    if failed:
                        msg += f" (failed in {failed})"
                    bot.send_message(chat_id, msg, reply_to_message_id=m.message_id)
                except Exception:
                    pass
                return True

            # Map aliases
            if cmd in ('togglekarma', 'togglepats'):
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                res = core.toggle_karma(c_user)
                if res:
                    try:
                        txt = rp.formatForTelegram(res)
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception as e:
                        logging.debug('toggle_karma reply failed: %s', e)
                return True
            if cmd in ('togglemedia',):
                try:
                    c_user = db.getUser(id=chat_id)
                except KeyError:
                    return True
                res = core.toggle_media(c_user)
                if res:
                    try:
                        txt = rp.formatForTelegram(res)
                        bot.send_message(chat_id, txt, parse_mode='HTML', reply_to_message_id=m.message_id)
                    except Exception as e:
                        logging.debug('toggle_media reply failed: %s', e)
                return True
        except Exception:
            logging.exception('Error handling command')
        return False

    @bot.message_handler(content_types=types)
    def _on_message(m):
        # Intercept commands so they are not broadcast to others
        if getattr(m, 'text', None) and str(m.text).startswith('/'):
            if _handle_command(m):
                return
        relay(m)

    # Reaction updates (both per-user and count updates)
    @bot.message_reaction_handler()
    def _on_reaction(m):
        try:
            # Log raw update if available
            logging.debug("Reaction update received")
            if hasattr(m, 'json'):
                logging.debug("reaction raw: %s", json.dumps(m.json, indent=2))

            chat_id = getattr(getattr(m, 'chat', None), 'id', None)
            msg_id = getattr(m, 'message_id', None)
            if not chat_id or not msg_id:
                logging.debug("reaction: missing chat/message id")
                return

            msid = ch.lookupMappingByData(msg_id, uid=chat_id)
            if msid is None:
                # Fallback to DB for cross-process support
                try:
                    msid = db.get_msid_by_uid_message(chat_id, msg_id, bot_id=BOT_ID)
                except Exception:
                    msid = None
                if msid is None:
                    logging.debug("reaction: no msid for chat=%s msg=%s", chat_id, msg_id)
                    return

            # Count updates don't include user; we only act on per-user updates
            user_obj = getattr(m, 'user', None)
            user_id = getattr(user_obj, 'id', None)
            if not user_id:
                return

            # Determine newly added emoji(s)
            added = []
            new_r = getattr(m, 'new_reaction', None)
            old_r = getattr(m, 'old_reaction', None)
            if isinstance(new_r, list):
                def _emoji_of(x):
                    if isinstance(x, dict):
                        return x.get('emoji') or x.get('value')
                    return getattr(x, 'emoji', None) or getattr(x, 'value', None)
                for r in new_r:
                    e = _emoji_of(r)
                    if e and (not isinstance(old_r, list) or all(_emoji_of(x) != e for x in old_r)):
                        added.append(e)

            # Fallback: some libs expose 'reaction' or 'message_reaction'
            if not added:
                r = getattr(m, 'message_reaction', None)
                if isinstance(r, list):
                    for x in r:
                        e = (x.get('emoji') if isinstance(x, dict) else getattr(x, 'emoji', None))
                        if e:
                            added.append(e)

            if not added:
                logging.debug("reaction: no added emojis detected")
                return

            # Process first added emoji
            emoji = str(added[0])
            logging.debug("Reaction detected: user=%s emoji=%s msid=%s", user_id, emoji, msid)
            
            try:
                c_user = db.getUser(id=user_id)
            except KeyError:
                logging.debug("reaction: unknown user %s", user_id)
                return

            # Mirror the reaction to all other users' copies of this message
            cm = ch.getMessage(msid)
            logging.debug("Lookup msid=%s -> found=%s sender=%s", msid, cm is not None, cm.user_id if cm else None)
            if cm:
                sender_id = cm.user_id
                mirrored_count = 0
                # Prefer cache when available; otherwise use DB mapping across processes
                recipient_pairs = []
                try:
                    # Gather from cache
                    for recipient in db.iterateUsers():
                        if not recipient.isJoined() or recipient.id == user_id:
                            continue
                        recipient_msg_id = ch.lookupMapping(recipient.id, msid=msid)
                        if recipient_msg_id:
                            recipient_pairs.append((recipient.id, recipient_msg_id))
                    # If nothing found in cache, try DB
                    if not recipient_pairs:
                        recipient_pairs = getattr(db, 'get_recipient_mappings_by_msid', lambda _msid, _bid=None: [])(msid, BOT_ID)
                        # filter out the reactor
                        recipient_pairs = [(uid, mid) for (uid, mid) in recipient_pairs if uid != user_id]
                except Exception:
                    pass

                for (rcpt_uid, rcpt_msg_id) in recipient_pairs:
                    try:
                        reaction_obj = ReactionTypeEmoji(emoji)
                        bot.set_message_reaction(
                            chat_id=rcpt_uid,
                            message_id=rcpt_msg_id,
                            reaction=[reaction_obj],
                            is_big=False
                        )
                        mirrored_count += 1
                    except Exception as e:
                        logging.warning("✗ Failed to mirror reaction to user %s: %s", rcpt_uid, e)
                logging.debug("Mirrored reaction to %d users (sender=%s)", mirrored_count, sender_id)

            # Update karma for the message sender
            res = core.handle_message_reaction(c_user, msid, emoji)
            logging.debug("handle_message_reaction returned: %s", res)
            if res:
                txt = rp.formatForTelegram(res)
                logging.debug("Formatted message for reactor prepared")
                try:
                    # Send confirmation to the reactor
                    bot.send_message(chat_id, txt, parse_mode="HTML", reply_to_message_id=msg_id)
                    logging.debug("Sent reaction confirmation to user %s", user_id)
                except Exception as e:
                    logging.warning("reaction: failed to send confirmation: %s", e)

        except Exception:
            logging.exception("reaction handler error")

    # Optional: lightweight debug tap
    # Removed debug tap handler
