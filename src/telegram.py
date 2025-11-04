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

# Globals initialized in init()
bot = None
db = None
ch = None
message_queue = None

# Config flags
allow_contacts = False
allow_documents = False
allow_polls = False


# Minimal Receiver to deliver system messages emitted by core
class _TelegramReceiver(core.Receiver):
    @staticmethod
    def reply(m, msid, who, except_who, reply_to):
        try:
            text = rp.formatForTelegram(m)
        except Exception as e:
            logging.warning("Failed to format system reply: %s", e)
            return

        def _uid(x):
            try:
                return x.id if hasattr(x, 'id') else int(x)
            except Exception:
                return None

        # Determine recipients
        recipients = []
        if who is None:
            for u in db.iterateUsers():
                try:
                    if not u.isJoined():
                        continue
                    if except_who is not None and _uid(except_who) == u.id:
                        continue
                    recipients.append(u.id)
                except Exception:
                    continue
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
        # Not used in this minimal receiver
        pass

    @staticmethod
    def stop_invoked(who, delete_out=False):
        # Not used in this minimal receiver
        pass

def log_into_channel(msg, html=False):
    # Deprecated helper; retained as no-op for backward compatibility
    pass


def _broadcast_targets(sender_id):
    """Yield users who should receive a forwarded copy (excludes sender and non-joined)."""
    for u in db.iterateUsers():
        try:
            if u.id == sender_id:
                continue
            if not u.isJoined():
                continue
            if u.isBlacklisted():
                continue
            yield u
        except Exception:
            continue


def send_to_single_inner(chat_id, ev, reply_to=None, force_caption=None):
    """Low-level send using the incoming Telegram message as source.
    Returns the Telegram message object."""
    kwargs = {}
    if reply_to is not None:
        kwargs["reply_to_message_id"] = reply_to
        kwargs["allow_sending_without_reply"] = True

    # Handle basic content types
    if hasattr(ev, 'content_type'):
        ct = ev.content_type
        if ct == 'text':
            return bot.send_message(chat_id, ev.text, **kwargs)
        if ct == 'photo' and ev.photo:
            photo = sorted(ev.photo, key=lambda p: p.width * p.height)[-1]
            return bot.send_photo(chat_id, photo.file_id, **kwargs)
        if ct == 'sticker':
            return bot.send_sticker(chat_id, ev.sticker.file_id, **kwargs)
        if ct == 'animation':
            return bot.send_animation(chat_id, ev.animation.file_id, **kwargs)
        if ct == 'audio':
            return bot.send_audio(chat_id, ev.audio.file_id, **kwargs)
        if ct == 'document':
            return bot.send_document(chat_id, ev.document.file_id, **kwargs)
        if ct == 'video':
            return bot.send_video(chat_id, ev.video.file_id, **kwargs)
        if ct == 'voice':
            return bot.send_voice(chat_id, ev.voice.file_id, **kwargs)
        if ct == 'video_note':
            return bot.send_video_note(chat_id, ev.video_note.file_id, **kwargs)
        if ct == 'location':
            return bot.send_location(chat_id, ev.location.latitude, ev.location.longitude, **kwargs)
        if ct == 'contact':
            return bot.send_contact(chat_id, ev.contact.phone_number, ev.contact.first_name, **kwargs)

    # Fallback: stringify
    return bot.send_message(chat_id, rp.formatForTelegram(rp.Reply(rp.types.CUSTOM, text=str(getattr(ev, 'text', '')))), parse_mode='HTML', **kwargs)


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

            # Don't thread original replies across users for now
            reply_to = None
            sent = send_to_single_inner(item.user.id, item.msg, reply_to, item.force_caption)
            if sent and hasattr(sent, 'message_id') and item.msid is not None:
                ch.saveMapping(item.user.id, item.msid, sent.message_id)
                try:
                    db.save_message_mapping(item.user.id, item.msid, sent.message_id)
                except Exception:
                    pass
        except Exception as e:
            logging.warning("Message delivery failed: %s", e)
            # If recent, retry once after short delay
            try:
                if time.time() - getattr(item, 'timestamp', 0) < 60:
                    time.sleep(0.5)
                    message_queue.put(0, item)
            except Exception:
                time.sleep(0.5)


def relay(message):
    """Main incoming message handler: forward to all active users (except sender)."""
    try:
        sender_id = message.from_user.id if hasattr(message, 'from_user') else message.chat.id
        # Update lastActive for the sender on any message
        try:
            with db.modifyUser(id=sender_id) as u:
                u.lastActive = datetime.datetime.now()
        except Exception:
            pass
        # Enforce admin media toggle: block media sending/forwarding for non-admins when enabled
        def _is_forward(msg):
            try:
                return bool(getattr(msg, 'forward_from', None) or getattr(msg, 'forward_from_chat', None) or (hasattr(msg, 'json') and msg.json.get('forward_origin')))
            except Exception:
                return False
        def _is_media(msg):
            ct = getattr(msg, 'content_type', '')
            return ct in {'photo','animation','document','video','sticker','voice','video_note','audio','poll'}

        try:
            user_obj = db.getUser(id=sender_id)
        except KeyError:
            user_obj = None

        if getattr(core, 'media_blocked', False) and (_is_media(message) or (_is_forward(message) and _is_media(message))):
            # allow admins to bypass
            if not (user_obj and user_obj.rank >= core.RANKS.admin):
                try:
                    txt = rp.formatForTelegram(rp.Reply(rp.types.ERR_MEDIA_DISABLED))
                    bot.send_message(sender_id, txt, parse_mode='HTML', reply_to_message_id=getattr(message, 'message_id', None))
                except Exception:
                    pass
                return
        # Cache original message for reactions/links
        cm = CachedMessage(user_id=sender_id)
        msid = ch.assignMessageId(cm)
        try:
            ch.saveMapping(sender_id, msid, message.message_id)
            db.save_message_mapping(sender_id, msid, message.message_id)
        except Exception:
            pass

        # Send to all targets
        for u in _broadcast_targets(sender_id):
            send_to_single(message, msid, u)

        logging.debug("relay(): msid=%d broadcast queued", msid)
    except Exception as e:
        logging.exception("Error in relay(): %s", e)


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
    global bot, db, ch, message_queue, allow_contacts, allow_documents, allow_polls

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
                    msid = db.get_msid_by_uid_message(chat_id, msg_id)
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
                        recipient_pairs = getattr(db, 'get_recipient_mappings_by_msid', lambda _msid: [])(msid)
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
