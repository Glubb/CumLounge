import logging
import sys
from datetime import datetime, timedelta
from threading import Lock

import src.replies as rp
from src.globals import *
from src.database import User, SystemConfig
from src.cache import CachedMessage
from src.util import genTripcode, getLastModFile

launched = None
is_leader = True

# User cache for frequent lookups
_user_cache = {}
_user_cache_time = {}
_USER_CACHE_TTL = 30

db = None
ch = None
spam_scores = None
sign_last_used = {} # uid -> datetime
vote_up_last_used = {} # uid -> datetime
vote_down_last_used = {} # uid -> datetime

reg_open = None
log_channel = None
karma_amount_add = None
karma_amount_remove = None
karma_level_names = None
bot_name = None
karma_is_pats = None
blacklist_contact = None
enable_signing = None
allow_remove_command = None
media_limit_period = None
sign_interval = None
vote_up_interval = None
vote_down_interval = None
media_blocked = False
media_auto_disable_hours = 8

def relay_message(message, user, msid, reply_msid):
	return None, msid

def init(config, _db, _ch):
	global launched, db, ch, spam_scores, reg_open, log_channel, karma_amount_add, karma_amount_remove, karma_level_names, blacklist_contact, bot_name, karma_is_pats, enable_signing, allow_remove_command, media_limit_period, sign_interval, vote_up_interval, vote_down_interval, media_blocked, media_auto_disable_hours, is_leader

	launched = datetime.now()

	db = _db
	ch = _ch
	spam_scores = ScoreKeeper()

	reg_open = config.get("reg_open", "")
	log_channel = config.get("log_channel", False)
	if log_channel:
		logging.info("Log channel: %d", log_channel)
	karma_amount_add = config.get("karma_amount_add", 2)
	karma_amount_remove = config.get("karma_amount_remove", 1)
	karma_level_names = config.get("karma_level_names", None)
	bot_name = config.get("bot_name", "")
	karma_is_pats = config.get("karma_is_pats", False)
	blacklist_contact = config.get("blacklist_contact", "")
	enable_signing = config["enable_signing"]
	allow_remove_command = config["allow_remove_command"]
	if "media_limit_period" in config.keys():
		media_limit_period = timedelta(hours=int(config["media_limit_period"]))
	sign_interval = timedelta(seconds=int(config.get("sign_limit_interval", 600)))
	vote_up_interval = timedelta(seconds=int(config.get("vote_up_limit_interval", 0)))
	vote_down_interval = timedelta(seconds=int(config.get("vote_down_limit_interval", 60)))

	media_blocked = bool(config.get("media_blocked", False))
	is_leader = bool(config.get("is_leader", True))
	try:
		media_auto_disable_hours = int(config.get("media_auto_disable_hours", 8))
	except Exception:
		media_auto_disable_hours = 8

	if config.get("locale"):
		rp.localization = __import__("src.replies_" + config["locale"],
			fromlist=["localization"]).localization

	if db.getSystemConfig() is None:
		c = SystemConfig()
		c.defaults()
		db.setSystemConfig(c)

def register_tasks(sched):
	sched.register(spam_scores.scheduledTask, seconds=SPAM_INTERVAL_SECONDS)
	def task():
		now = datetime.now()
		for user in db.iterateUsers():
			if not user.isJoined():
				continue
			if user.warnExpiry is not None and now >= user.warnExpiry:
				with db.modifyUser(id=user.id) as user:
					user.removeWarning()
	sched.register(task, minutes=15)

	def _auto_disable_media():
		global media_blocked
		try:
			if media_auto_disable_hours and media_auto_disable_hours > 0:
				threshold = datetime.now() - timedelta(hours=media_auto_disable_hours)
				latest_admin = None
				for u in db.iterateUsers():
					try:
						if not u.isJoined() or u.rank < RANKS.admin:
							continue
						t = getattr(u, 'lastActive', None)
						if t is None:
							continue
						if latest_admin is None or t > latest_admin:
							latest_admin = t
					except Exception:
						continue
				if (latest_admin is None or latest_admin < threshold) and (not media_blocked):
					media_blocked = True
					Sender.reply(rp.Reply(rp.types.CUSTOM, text="Media has been automatically disabled due to no admin activity."), None, None, None, None)
		except Exception:
			logging.exception("Error in auto-disable media task")

	if is_leader:
		sched.register(_auto_disable_media, minutes=30)

def updateUserFromEvent(user, c_user):
	user.username = c_user.username
	user.realname = c_user.realname
	user.lastActive = datetime.now()

def _get_cached_user(uid):
	"""Get user with caching to reduce DB queries."""
	global _user_cache, _user_cache_time
	now = datetime.now()
	
	if uid in _user_cache:
		cached_time = _user_cache_time.get(uid)
		if cached_time and (now - cached_time).total_seconds() < _USER_CACHE_TTL:
			return _user_cache[uid]
	
	try:
		user = db.getUser(id=uid)
		_user_cache[uid] = user
		_user_cache_time[uid] = now
		return user
	except KeyError:
		return None

def _invalidate_user_cache(uid):
	"""Invalidate cached user data."""
	global _user_cache, _user_cache_time
	_user_cache.pop(uid, None)
	_user_cache_time.pop(uid, None)

def getUserByName(username):
	if not username:
		return None
	username = username.lstrip('@').lower()
	for user in db.iterateUsers():
		if user.username is not None and user.username.lower() == username:
			return user
	return None

def getUserByOid(oid):
	for user in db.iterateUsers():
		if not user.isJoined():
			continue
		if user.getObfuscatedId() == oid:
			return user
	return None

def getRecentlyActiveUsers():
	users = db.iterateUsers()
	cache_start_datetime = max(launched, datetime.now() - timedelta(hours=24))
	count = 0
	for user in users:
		if (user.lastActive is not None) and (user.lastActive > cache_start_datetime):
			count += 1
	return count

def getKarmaLevel(karma):
	karma_level = 0
	while (karma_level < len(KARMA_LEVELS)) and (karma >= KARMA_LEVELS[karma_level]):
		karma_level += 1
	return karma_level

def getKarmaLevelName(karma):
	if karma_level_names is not None:
		assert len(karma_level_names) == len(KARMA_LEVELS) + 1
		return karma_level_names[getKarmaLevel(karma)]
	return ""

def requireUser(func):
	def wrapper(c_user, *args, **kwargs):
		if isinstance(c_user, User):
			user = c_user
		else:
			try:
				user = db.getUser(id=c_user.id)
			except KeyError as e:
				return rp.Reply(rp.types.USER_NOT_IN_CHAT, bot_name=bot_name)

		with db.modifyUser(id=user.id) as user:
			updateUserFromEvent(user, c_user)
		_invalidate_user_cache(user.id)

		if user.isBlacklisted():
			return rp.Reply(rp.types.ERR_BLACKLISTED, reason=user.blacklistReason, contact=blacklist_contact)
		elif not user.isJoined():
			return rp.Reply(rp.types.USER_NOT_IN_CHAT, bot_name=bot_name)

		return func(user, *args, **kwargs)
	return wrapper

def requireRank(need_rank):
	def f(func):
		def wrapper(user, *args, **kwargs):
			if not isinstance(user, User):
				raise SyntaxError("you fucked up the decorator order")
			if user.rank < need_rank:
				return
			return func(user, *args, **kwargs)
		return wrapper
	return f

def requireAdmin(func):
	def wrapper(*args, **kwargs):
		if len(args) > 0 and isinstance(args[0], User):
			user = args[0]
		else:
			user = kwargs.get('user', None)
		if user is None or user.rank < RANKS.admin:
			return rp.Reply(rp.types.ERR_COMMAND_DISABLED)
		return func(*args, **kwargs)
	return wrapper

###

# RAM cache for spam scores

class ScoreKeeper():
	def __init__(self):
		self.lock = Lock()
		self.scores = {}
	def increaseSpamScore(self, uid, n):
		with self.lock:
			s = self.scores.get(uid, 0)
			if s > SPAM_LIMIT:
				return False
			elif s + n > SPAM_LIMIT:
				self.scores[uid] = SPAM_LIMIT_HIT
				return s + n <= SPAM_LIMIT_HIT
			self.scores[uid] = s + n
			return True
	def scheduledTask(self):
		with self.lock:
			for uid in list(self.scores.keys()):
				s = self.scores[uid] - 1
				if s <= 0:
					del self.scores[uid]
				else:
					self.scores[uid] = s

###

# Event receiver template and Sender class that fwds to all registered event receivers

class Receiver():
	@staticmethod
	def reply(m: rp.Reply, msid: int, who, except_who, reply_to: bool):
		raise NotImplementedError()
	@staticmethod
	def delete(msids: list[int]):
		raise NotImplementedError()
	@staticmethod
	def stop_invoked(who, delete_out: bool):
		raise NotImplementedError()

class Sender(Receiver): # flawless class hierachy I know...
	receivers = []
	@staticmethod
	def reply(m, msid, who, except_who, reply_to):
		logging.debug("reply(m.type=%s, msid=%r, reply_to=%r)", rp.types.reverse[m.type], msid, reply_to)
		for r in Sender.receivers:
			r.reply(m, msid, who, except_who, reply_to)
	@staticmethod
	def delete(msids):
		logging.debug("delete(msids=%r)", msids)
		for r in Sender.receivers:
			r.delete(msids)
	@staticmethod
	def stop_invoked(who, delete_out=False):
		logging.debug("stop_invoked(who=%s)", who)
		for r in Sender.receivers:
			r.stop_invoked(who, delete_out)

def registerReceiver(obj):
	assert issubclass(obj, Receiver)
	Sender.receivers.append(obj)
	return obj

####

def user_join(c_user):
	try:
		user = db.getUser(id=c_user.id)
	except KeyError as e:
		user = None

	if user is not None:
		# check if user can't rejoin
		err = None
		if user.isBlacklisted():
			err = rp.Reply(rp.types.ERR_BLACKLISTED, reason=user.blacklistReason, contact=blacklist_contact)
		elif user.isJoined():
			err = rp.Reply(rp.types.USER_IN_CHAT, bot_name=bot_name)
		if err is not None:
			with db.modifyUser(id=user.id) as user:
				updateUserFromEvent(user, c_user)
			return err
		# user rejoins
		with db.modifyUser(id=user.id) as user:
			updateUserFromEvent(user, c_user)
			user.setLeft(False)
		logging.info("%s rejoined chat", user)
		return rp.Reply(rp.types.CUSTOM, text="You joined the anonymous chat")

	if not reg_open:
		return rp.Reply(rp.types.ERR_REG_CLOSED)

	# create new user
	user = User()
	user.defaults()
	user.id = c_user.id
	updateUserFromEvent(user, c_user)
	ret = []
	if not any(db.iterateUserIds()):
		user.rank = RANKS.admin
		ret.append(rp.Reply(rp.types.CHAT_JOIN_FIRST, bot_name=bot_name))

	logging.info("%s joined chat", user)
	db.addUser(user)
	ret.insert(0, rp.Reply(rp.types.CUSTOM, text="You joined the anonymous chat"))

	motd = db.getSystemConfig().motd
	if motd != "":
		ret.append(rp.Reply(rp.types.CUSTOM, text=motd))

	return ret

def force_user_leave(user_id, blocked=True):
	with db.modifyUser(id=user_id) as user:
		user.setLeft()
	if blocked:
		logging.warning("Force leaving %s because bot is blocked", user)
	Sender.stop_invoked(user)

@requireUser
def user_leave(user):
	force_user_leave(user.id, blocked=False)
	logging.info("%s left chat", user)

	return rp.Reply(rp.types.CUSTOM, text="You left the anonymous chat")

@requireUser
def get_info(user):
	params = {
		"id": user.getObfuscatedId(),
		"username": user.getFormattedName(),
		"rank_i": user.rank,
		"rank": RANKS.reverse[user.rank],
		"karma_is_pats": karma_is_pats,
		"karma": user.karma,
		"karmalevel": getKarmaLevelName(user.karma),
		"warnings": user.warnings,
		"warnExpiry": user.warnExpiry,
		"cooldown": user.cooldownUntil if user.isInCooldown() else None,
	}
	return rp.Reply(rp.types.USER_INFO, **params)

@requireUser
@requireRank(RANKS.mod)
def get_info_mod(user, msid):
	cm = ch.getMessage(msid)
	if cm is None or cm.user_id is None:
		return rp.Reply(rp.types.ERR_NOT_IN_CACHE)

	user2 = db.getUser(id=cm.user_id)
	params = {
		"id": user2.getObfuscatedId(),
		"rank_i": user2.rank,
		"rank": RANKS.reverse[user2.rank],
		"karma": user2.karma if user.rank >= RANKS.admin else user2.getObfuscatedKarma(),
		"karma_is_pats": karma_is_pats,
		"karma_obfuscated": user.rank < RANKS.admin,
		"warnings": user2.warnings,
		"warnExpiry": user2.warnExpiry,
		"cooldown": user2.cooldownUntil if user2.isInCooldown() else None,
	}
	return rp.Reply(rp.types.USER_INFO_MOD, **params)

@requireUser
def get_karma_info(user):
	karma = user.karma
	karma_level = getKarmaLevel(karma)
	next_level_karma = KARMA_LEVELS[karma_level] if karma_level < len(KARMA_LEVELS) else None
	params = {
		"karma": karma,
		"karma_is_pats": karma_is_pats,
		"level_name": getKarmaLevelName(karma),
		"level_karma": KARMA_LEVELS[karma_level - 1] if karma_level > 0 else None,
		"next_level_name": getKarmaLevelName(next_level_karma) if next_level_karma is not None else "???",
		"next_level_karma": next_level_karma
	}
	return rp.Reply(rp.types.KARMA_INFO, **params)

@requireUser
@requireRank(RANKS.admin)
def get_bot_info(user):
	params = {
		"python_ver": sys.version,
		"os": sys.platform,
		"last_file_mod":
			max(
				getLastModFile(),
				getLastModFile("src"),
				getLastModFile("util"),
				key=lambda file: file["last_mod"]
			)["last_mod"],
		"launched": launched,
		"time": format_datetime(datetime.now(), True),
		"cached_msgs": len(ch.msgs),
		"active_users": getRecentlyActiveUsers()
	}
	return rp.Reply(rp.types.BOT_INFO, **params)

@requireUser
def get_users(user):
	active, inactive, black, cooldown = 0, 0, 0, 0
	for user2 in db.iterateUsers():
		if user2.isBlacklisted():
			black += 1
		elif not user2.isJoined():
			inactive += 1
		else:
			active += 1
		if user2.isInCooldown():
			cooldown += 1
	if user.rank < RANKS.mod:
		return rp.Reply(rp.types.USERS_INFO,
        	active=active, inactive=inactive + black, total=active + inactive + black)
	return rp.Reply(rp.types.USERS_INFO_EXTENDED,
		active=active, inactive=inactive + black, blacklisted=black,
		total=active + inactive + black, cooldown=cooldown)

@requireUser
@requireRank(RANKS.admin)
def set_commands_dict(user, arg):
	cmds = {
		cmd[0].strip().lower(): cmd[1].strip() for cmd in [
			cmd.split("-", 1) for cmd in arg.split("\n")
			if cmd.strip() != ""
		]
	}
	return cmds

@requireUser
def get_rules(user):
	motd = db.getSystemConfig().motd
	if motd == "": return
	return rp.Reply(rp.types.CUSTOM, text=motd)

@requireUser
@requireRank(RANKS.admin)
def set_rules(user, arg):
	with db.modifySystemConfig() as config:
		config.motd = arg
	logging.info("%s set rules to: %r", user, arg)
	return rp.Reply(rp.types.SUCCESS_RULES, bot_name=bot_name)

@requireUser
def toggle_debug(user):
	with db.modifyUser(id=user.id) as user:
		user.debugEnabled = not user.debugEnabled
		new = user.debugEnabled
	return rp.Reply(rp.types.BOOLEAN_CONFIG, description="Debug mode", enabled=new)

@requireUser
def toggle_karma(user):
	with db.modifyUser(id=user.id) as user:
		user.hideKarma = not user.hideKarma
		new = user.hideKarma
	return rp.Reply(rp.types.BOOLEAN_CONFIG, description=("Pat" if karma_is_pats else "Karma") + " notifications", enabled=not new)

@requireUser
@requireAdmin
def toggle_media(user):
    global media_blocked
    media_blocked = not media_blocked
    return rp.Reply(rp.types.BOOLEAN_CONFIG, description="Media messages", enabled=not media_blocked)

@requireUser
def get_tripcode(user):
	if not enable_signing:
		return rp.Reply(rp.types.ERR_COMMAND_DISABLED)

	return rp.Reply(rp.types.TRIPCODE_INFO, tripcode=user.tripcode)

@requireUser
def set_tripcode(user, text):
	if not enable_signing:
		return rp.Reply(rp.types.ERR_COMMAND_DISABLED)

	if not (0 < text.find("#") < len(text) - 1):
		return rp.Reply(rp.types.ERR_INVALID_TRIP_FORMAT)
	if "\n" in text or len(text) > 30:
		return rp.Reply(rp.types.ERR_INVALID_TRIP_FORMAT)

	with db.modifyUser(id=user.id) as user:
		user.tripcode = text
	tripname, tripcode = genTripcode(user.tripcode)
	return rp.Reply(rp.types.TRIPCODE_SET, tripname=tripname, tripcode=tripcode)

@requireUser
@requireRank(RANKS.admin)
def promote_user(user, username2, rank):
	user2 = getUserByName(username2)
	if user2 is None:
		return rp.Reply(rp.types.ERR_NO_USER)

	if user2.rank >= rank:
		return
	with db.modifyUser(id=user2.id) as user2:
		user2.rank = rank
	if rank >= RANKS.admin:
		_push_system_message(rp.Reply(rp.types.PROMOTED_ADMIN), who=user2)
	elif rank >= RANKS.mod:
		_push_system_message(rp.Reply(rp.types.PROMOTED_MOD), who=user2)
	logging.info("%s was promoted by %s to: %d", user2, user, rank)
	return rp.Reply(rp.types.SUCCESS)

@requireUser
@requireRank(RANKS.admin)
def demote_user(user, username2):
	"""Demote a user back to regular user rank.
	Guardrails: cannot demote users with rank >= invoker's rank; refuse if blacklisted.
	"""
	user2 = getUserByName(username2)
	if user2 is None:
		return rp.Reply(rp.types.ERR_NO_USER)
	# Don't silently unblacklist via demotion
	if user2.isBlacklisted():
		return rp.Reply(rp.types.ERR_COMMAND_DISABLED)
	# Prevent demoting same or higher rank than invoker
	if user2.rank >= user.rank:
		return
	with db.modifyUser(id=user2.id) as user2:
		user2.rank = RANKS.user
	_push_system_message(rp.Reply(rp.types.CUSTOM, text="Your privileges have been revoked; you are now a user."), who=user2)
	logging.info("%s was demoted to user by %s", user2, user)
	return rp.Reply(rp.types.SUCCESS)

@requireUser
@requireRank(RANKS.mod)
def send_mod_message(user, arg):
	text = arg + " ~<b>mods</b>"
	m = rp.Reply(rp.types.CUSTOM, text=text)
	_push_system_message(m)
	logging.info("%s sent mod message: %s", user, arg)

@requireUser
@requireRank(RANKS.admin)
def send_admin_message(user, arg):
	text = arg + " ~<b>admins</b>"
	m = rp.Reply(rp.types.CUSTOM, text=text)
	_push_system_message(m)
	logging.info("%s sent admin message: %s", user, arg)

# NOTE: The finalized handle_message_reaction implementation appears below.

@requireUser
@requireRank(RANKS.mod)
def warn_user(user, msid, delete=False, del_all=False, duration=""):
	cm = ch.getMessage(msid)
	if cm is None or cm.user_id is None:
		return rp.Reply(rp.types.ERR_NOT_IN_CACHE)

	d = None
	if not cm.warned:
		with db.modifyUser(id=cm.user_id) as user2:
			if duration == "":
				d = user2.addWarning()
			else:
				cooldown = {
					"seconds": 0,
					"minutes": 0,
					"hours": 0,
					"days": 0,
					"weeks": 0
				}
				cooldown_keys = {
					"s": "seconds",
					"m": "minutes",
					"h": "hours",
					"d": "days",
					"w": "weeks",
					"sec": "seconds",
					"min": "minutes"
				}
				i = 0
				while i < len(duration):
					n = ""
					while (i < len(duration)) and (duration[i] == " "):
						i += 1
					while (i < len(duration)) and (duration[i] >= "0") and (duration[i] <= "9"):
						n += duration[i]
						i += 1
					while (i < len(duration)) and (duration[i] == " "):
						i += 1
					if not (duration[i].lower() in cooldown_keys):
						return rp.Reply(rp.types.ERR_INVALID_DURATION)
					key = cooldown_keys[duration[i]]
					if (cooldown[key] != 0) or not n.isnumeric():
						return rp.Reply(rp.types.ERR_INVALID_DURATION)
					cooldown[key] = int(n)
					i += 1
				d = user2.addWarning(timedelta(**cooldown))
			user2.karma -= KARMA_WARN_PENALTY
		_push_system_message(
			rp.Reply(rp.types.GIVEN_COOLDOWN, duration=d, deleted=delete),
			who=user2, reply_to=msid)
		cm.warned = True
	else:
		user2 = db.getUser(id=cm.user_id)
		if not delete: # allow deleting already warned messages
			return rp.Reply(rp.types.ERR_ALREADY_WARNED)
	if delete:
		if del_all:
			msgs = ch.getMessages(cm.user_id)
			for cm2 in msgs:
				Sender.delete([cm2])
			if d is not None:
				logging.info("%s warned %s (cooldown: %s) and deleted all %d messages", user, user2.getObfuscatedId(), d, len(msgs))
			else:
				logging.info("%s warned %s and deleted all %d messages", user, user2.getObfuscatedId(), len(msgs))
			return rp.Reply(rp.types.SUCCESS_WARN_DELETEALL, id=user2.getObfuscatedId(), count=len(msgs), cooldown=d)
		else:
			Sender.delete([msid])
			if d is not None:
				logging.info("%s warned %s (cooldown: %s) and deleted a message", user, user2.getObfuscatedId(), d)
			else:
				logging.info("%s warned %s and deleted a message", user, user2.getObfuscatedId())
			return rp.Reply(rp.types.SUCCESS_WARN_DELETE, id=user2.getObfuscatedId(), cooldown=d)
	else:
		if d is not None:
			logging.info("%s warned %s (cooldown: %s)", user, user2.getObfuscatedId(), d)
		else:
			logging.info("%s warned %s", user, user2.getObfuscatedId())
		return rp.Reply(rp.types.SUCCESS_WARN, id=user2.getObfuscatedId(), cooldown=d)

@requireUser
@requireRank(RANKS.mod)
def delete_message(user, msid, del_all=False):
	if not allow_remove_command:
		return rp.Reply(rp.types.ERR_COMMAND_DISABLED)

	cm = ch.getMessage(msid)
	if cm is None or cm.user_id is None:
		return rp.Reply(rp.types.ERR_NOT_IN_CACHE)

	user2 = db.getUser(id=cm.user_id)

	if del_all:
		msgs = ch.getMessages(user2.id)
		for cm2 in msgs:
			Sender.delete([cm2])
		logging.info("%s deleted all messages from %s", user, user2.getObfuscatedId())
		return rp.Reply(rp.types.SUCCESS_DELETEALL, id=user2.getObfuscatedId(), count=len(msgs))
	else:
		_push_system_message(rp.Reply(rp.types.MESSAGE_DELETED), who=user2, reply_to=msid)
		Sender.delete([msid])
		logging.info("%s deleted a message from %s", user, user2.getObfuscatedId())
		return rp.Reply(rp.types.SUCCESS_DELETE, id=user2.getObfuscatedId())

@requireUser
@requireRank(RANKS.admin)
def cleanup_messages(user):
	msids = []
	def f(msid: int, cm: CachedMessage):
		if cm.user_id is None:
			return
		if 1337 in cm.upvoted: # mark that we've been here before
			return
		user2 = db.getUser(id=cm.user_id)
		if user2.isBlacklisted():
			msids.append(msid)
			cm.upvoted.add(1337)
	ch.iterateMessages(f)
	logging.info("%s invoked cleanup (matched: %d)", user, len(msids))
	Sender.delete(msids)
	return rp.Reply(rp.types.DELETION_QUEUED, count=len(msids))

@requireUser
@requireRank(RANKS.admin)
def uncooldown_user(user, oid2=None, username2=None):
	if oid2 is not None:
		user2 = getUserByOid(oid2)
		if user2 is None:
			return rp.Reply(rp.types.ERR_NO_USER_BY_ID)
	elif username2 is not None:
		user2 = getUserByName(username2)
		if user2 is None:
			return rp.Reply(rp.types.ERR_NO_USER)
	else:
		raise ValueError()

	if not user2.isInCooldown():
		return rp.Reply(rp.types.ERR_NOT_IN_COOLDOWN)
	with db.modifyUser(id=user2.id) as user2:
		user2.removeWarning()
		was_until = user2.cooldownUntil
		user2.cooldownUntil = None
	logging.info("%s removed cooldown from %s (was until %s)", user, user2, format_datetime(was_until))
	return rp.Reply(rp.types.SUCCESS)

@requireUser
@requireRank(RANKS.mod)
def blacklist_user(user, msid, reason, del_all=False):
	cm = ch.getMessage(msid)
	if cm is None or cm.user_id is None:
		return rp.Reply(rp.types.ERR_NOT_IN_CACHE)

	with db.modifyUser(id=cm.user_id) as user2:
		if user2.rank >= user.rank:
			return
		user2.setBlacklisted(reason)
	cm.warned = True
	Sender.stop_invoked(user2, True) # do this before queueing new messages below
	_push_system_message(
		rp.Reply(rp.types.ERR_BLACKLISTED, reason=reason, contact=blacklist_contact),
		who=user2, reply_to=msid)
	if del_all:
		msgs = ch.getMessages(cm.user_id)
		for cm2 in msgs:
			Sender.delete([cm2])
		logging.info("%s was blacklisted by %s and all his messages were deleted for: %s", user2, user, reason)
		return rp.Reply(rp.types.SUCCESS_BLACKLIST_DELETEALL, id=user2.getObfuscatedId(), count=len(msgs))
	else:
		Sender.delete([msid])
		logging.info("%s was blacklisted by %s for: %s", user2, user, reason)
		return rp.Reply(rp.types.SUCCESS_BLACKLIST, id=user2.getObfuscatedId())

@requireUser
@requireRank(RANKS.admin)
def unblacklist_user(user, username):
    if username is None:
        return rp.Reply(rp.types.ERR_NO_ARG)
    
    username = username.lstrip('@')
    user2 = getUserByName(username)
    if user2 is None:
        logging.warning("Failed unblacklist attempt by %s: user %s not found", user, username)
        return rp.Reply(rp.types.ERR_NO_USER)
    
    if not user2.isBlacklisted():
        logging.info("Failed unblacklist attempt by %s: user %s is not blacklisted", user, user2.getFormattedName())
        return rp.Reply(rp.types.ERR_NOT_BLACKLISTED)
    
    old_reason = user2.blacklistReason
    with db.modifyUser(id=user2.id) as user2:
        user2.setJoined()
    
    logging.info("%s unblacklisted %s (previous reason: %s)", 
                 user.getFormattedName(), user2.getFormattedName(), old_reason or "None")
    return rp.Reply(rp.types.SUCCESS_UNBLACKLIST, id=user2.getFormattedName())

@requireUser
def handle_message_reaction(user, msid, emoji):
	cm = ch.getMessage(msid)
	if cm is None or cm.user_id is None:
		return rp.Reply(rp.types.ERR_NOT_IN_CACHE)

	if cm.user_id == user.id:
		return rp.Reply(rp.types.ERR_VOTE_OWN_MESSAGE)

	sender = _get_cached_user(cm.user_id)
	if not sender:
		return rp.Reply(rp.types.ERR_NOT_IN_CACHE)

	_norm = lambda e: e.replace('\uFE0F', '') if e else e
	pos_norm = {_norm(x) for x in POSITIVE_REACTIONS}
	norm = _norm(emoji)

	if norm in pos_norm:
		karma_change = karma_amount_add
		is_pat = emoji in {"❤️", "🥰", "💖", "💗", "💓", "💝"}
		result = modify_karma(user, msid, karma_change, emoji=emoji, karma_is_pats=is_pat)
		if result.type == rp.types.ERR_VOTE_OWN_MESSAGE:
			return result
		
		if not sender.hideKarma:
			notification = rp.Reply(rp.types.SUCCESS_EMOJI_RECEIVED, 
				karma_change=karma_change, emoji=emoji, karma_is_pats=is_pat)
			_push_system_message(notification, who=sender, reply_to=msid)
		
		return rp.Reply(rp.types.SUCCESS_EMOJI_REACTION, karma_change=karma_change, emoji=emoji, karma_is_pats=is_pat, bot_name=bot_name)

	if norm in {_norm("👎"), _norm("💩")}:
		karma_change = -karma_amount_remove
		result = modify_karma(user, msid, karma_change, emoji=emoji)
		if result.type == rp.types.ERR_VOTE_OWN_MESSAGE:
			return result
		
		if not sender.hideKarma:
			notification = rp.Reply(rp.types.SUCCESS_EMOJI_RECEIVED, 
				karma_change=karma_change, emoji=emoji, karma_is_pats=False)
			_push_system_message(notification, who=sender, reply_to=msid)
		
		return rp.Reply(rp.types.SUCCESS_EMOJI_REACTION, karma_change=karma_change, emoji=emoji, karma_is_pats=False, bot_name=bot_name)

	return None

@requireUser
def modify_karma(user, msid, amount, emoji=None, karma_is_pats=False):
	cm = ch.getMessage(msid)
	if cm is None or cm.user_id is None:
		return rp.Reply(rp.types.ERR_NOT_IN_CACHE)
	
	user2 = _get_cached_user(cm.user_id)
	if not user2:
		return rp.Reply(rp.types.ERR_NOT_IN_CACHE)
	
	if user2.id == user.id:
		return rp.Reply(rp.types.ERR_VOTE_OWN_MESSAGE)

	params = {"karma_is_pats": karma_is_pats}
	
	if cm.hasUpvoted(user):
		return rp.Reply(rp.types.ERR_ALREADY_VOTED_UP, **params)
	if cm.hasDownvoted(user):
		return rp.Reply(rp.types.ERR_ALREADY_VOTED_DOWN, **params)
	
	if amount > 0:
		if vote_up_interval.total_seconds() > 1:
			last_used = vote_up_last_used.get(user.id, None)
			if last_used and (datetime.now() - last_used) < vote_up_interval:
				return rp.Reply(rp.types.ERR_SPAMMY_VOTE_UP, **params)
			vote_up_last_used[user.id] = datetime.now()

		cm.addUpvote(user)
	elif amount < 0:
		if vote_down_interval.total_seconds() > 1:
			last_used = vote_down_last_used.get(user.id, None)
			if last_used and (datetime.now() - last_used) < vote_down_interval:
				return rp.Reply(rp.types.ERR_SPAMMY_VOTE_DOWN, **params)
			vote_down_last_used[user.id] = datetime.now()

		cm.addDownvote(user)
	else:
		return

	with db.modifyUser(id=user2.id) as user2:
		user2.karma += amount
	_invalidate_user_cache(user2.id)
		
	if emoji:
		params = {"karma_is_pats": karma_is_pats, "karma_change": amount, "emoji": emoji}
		return rp.Reply(rp.types.SUCCESS_EMOJI_REACTION, **params)
	else:
		return rp.Reply(rp.types.SUCCESS_KARMA_REACTION, karma_change=amount)

@requireUser
def prepare_user_message(user: User, msg_score, *, is_media=False, signed=False, tripcode=False, ksigned=False):
	if user.isInCooldown():
		return rp.Reply(rp.types.ERR_COOLDOWN, until=user.cooldownUntil)
	if (signed or tripcode or ksigned) and not enable_signing:
		return rp.Reply(rp.types.ERR_COMMAND_DISABLED)
	if tripcode and user.tripcode is None:
		return rp.Reply(rp.types.ERR_NO_TRIPCODE)
	if is_media and user.rank < RANKS.mod and media_limit_period is not None:
		if (datetime.now() - user.joined) < media_limit_period:
			return rp.Reply(rp.types.ERR_MEDIA_LIMIT, media_limit_period=media_limit_period)

	ok = spam_scores.increaseSpamScore(user.id, msg_score)
	if not ok:
		return rp.Reply(rp.types.ERR_SPAMMY)

	if (signed or ksigned) and sign_interval.total_seconds() > 1:
		last_used = sign_last_used.get(user.id, None)
		if last_used and (datetime.now() - last_used) < sign_interval:
			return rp.Reply(rp.types.ERR_SPAMMY_SIGN)
		sign_last_used[user.id] = datetime.now()

	return ch.assignMessageId(CachedMessage(user.id))

def _push_system_message(m, *, who=None, except_who=None, reply_to=None):
	msid = None
	if who is None:
		msid = ch.assignMessageId(CachedMessage())
	Sender.reply(m, msid, who, except_who, reply_to)
