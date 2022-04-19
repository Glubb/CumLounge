import re
from string import Formatter

from src.globals import *

class NumericEnum(Enum):
	def __init__(self, names):
		d = {name: i for i, name in enumerate(names)}
		super(NumericEnum, self).__init__(d)

class CustomFormatter(Formatter):
	def convert_field(self, value, conversion):
		if conversion == "x": # escape
			return escape_html(value)
		elif conversion == "t": # date[t]ime
			return format_datetime(value)
		elif conversion == "d": # time[d]elta
			return format_timedelta(value)
		return super(CustomFormatter, self).convert_field(value, conversion)

# definition of reply class and types

class Reply():
	def __init__(self, type, **kwargs):
		self.type = type
		self.kwargs = kwargs

types = NumericEnum([
	"CUSTOM",
	"SUCCESS",
	"SUCCESS_DELETE",
	"SUCCESS_DELETEALL",
	"SUCCESS_WARN_DELETE",
	"SUCCESS_WARN_DELETEALL",
	"SUCCESS_BLACKLIST",
	"SUCCESS_BLACKLIST_DELETEALL",
	"BOOLEAN_CONFIG",

	"CHAT_JOIN",
	"CHAT_LEAVE",
	"USER_IN_CHAT",
	"USER_NOT_IN_CHAT",
	"GIVEN_COOLDOWN",
	"MESSAGE_DELETED",
	"PROMOTED_MOD",
	"PROMOTED_ADMIN",
	"KARMA_THANK_YOU",
	"KARMA_NOTIFICATION",
	"TRIPCODE_INFO",
	"TRIPCODE_SET",

	"ERR_COMMAND_DISABLED",
	"ERR_NO_REPLY",
	"ERR_NOT_IN_CACHE",
	"ERR_NO_USER",
	"ERR_NO_USER_BY_ID",
	"ERR_ALREADY_WARNED",
	"ERR_NOT_IN_COOLDOWN",
	"ERR_COOLDOWN",
	"ERR_BLACKLISTED",
	"ERR_ALREADY_UPVOTED",
	"ERR_UPVOTE_OWN_MESSAGE",
	"ERR_SPAMMY",
	"ERR_SPAMMY_SIGN",
	"ERR_SIGN_PRIVACY",
	"ERR_INVALID_TRIP_FORMAT",
	"ERR_NO_TRIPCODE",
	"ERR_MEDIA_LIMIT",

	"USER_INFO",
	"USER_INFO_MOD",
	"USERS_INFO",
	"USERS_INFO_EXTENDED",

	"PROGRAM_VERSION",
	"HELP",
])

# formatting of these as user-readable text

def em(s):
	# make commands clickable by excluding them from the formatting
	s = re.sub(r'[^a-z0-9_-]/[A-Za-z]+\b', r'</em>\g<0><em>', s)
	return "<em>" + s + "</em>"

def smiley(n):
	if n <= 0: return ":)"
	elif n == 1: return ":|"
	elif n <= 3: return ":/"
	else: return ":("

format_strs = {
	types.CUSTOM: "{text}",
	types.SUCCESS: "☑",
	types.SUCCESS_DELETE: "☑ The message by <b>{id}</b> has been deleted",
    types.SUCCESS_DELETEALL: "☑ All {count} messages by <b>{id}</b> have been deleted",
	types.SUCCESS_WARN_DELETE: "☑ <b>{id}</b> has been warned and the message was deleted",
	types.SUCCESS_WARN_DELETEALL: "☑ <b>{id}</b> has been warned and all {count} messages were deleted",
	types.SUCCESS_BLACKLIST: "☑ <b>{id}</b> has been blacklisted and the message was deleted",
	types.SUCCESS_BLACKLIST_DELETEALL: "☑ <b>{id}</b> has been blacklisted and all {count} messages were deleted",
	types.BOOLEAN_CONFIG: lambda enabled, **_:
		"<b>{description!x}</b>: " + (enabled and "enabled" or "disabled"),

	types.CHAT_JOIN: em("You joined the cat lounge!"),
	types.CHAT_LEAVE: em("You left the cat lounge!"),
	types.USER_IN_CHAT: em("You're already in the cat lounge."),
	types.USER_NOT_IN_CHAT: em("You're not in the cat lounge yet. Use /start to join!"),
	types.GIVEN_COOLDOWN: lambda deleted, **_:
		em( "You've been handed a cooldown of {duration!d} for this message"+
			(deleted and " (message also deleted)" or "") ),
	types.MESSAGE_DELETED:
		em( "Your message has been deleted. No cooldown has been "
			"given this time, but refrain from posting it again." ),
	types.PROMOTED_MOD: em("You've been promoted to moderator, run /modhelp for a list of commands."),
	types.PROMOTED_ADMIN: em("You've been promoted to admin, run /adminhelp for a list of commands."),
	types.KARMA_THANK_YOU: em("You just gave this cat some nice pats, awesome!"),
	types.KARMA_NOTIFICATION:
		em( "You've just been given nice pats! (check /info to see your pats"+
			" or /togglepats to turn these notifications off)" ),
	types.TRIPCODE_INFO: lambda tripcode, **_:
		"<b>tripcode</b>: " + ("<code>{tripcode!x}</code>" if tripcode is not None else "unset"),
	types.TRIPCODE_SET: em("Tripcode set. It will appear as: ") + "<b>{tripname!x}</b> <code>{tripcode!x}</code>",

	types.ERR_COMMAND_DISABLED: em("This command has been disabled."),
	types.ERR_NO_REPLY: em("You need to reply to a message to use this command."),
	types.ERR_NOT_IN_CACHE: em("Message not found in cache... (24h passed or bot was restarted)"),
	types.ERR_NO_USER: em("No user found by that name!"),
	types.ERR_NO_USER_BY_ID: em("No user found by that id! Note that all ids rotate every 24 hours."),
	types.ERR_COOLDOWN: em("Your cooldown expires at {until!t}"),
	types.ERR_ALREADY_WARNED: em("A warning has already been issued for this message."),
	types.ERR_NOT_IN_COOLDOWN: em("This user is not in a cooldown right now."),
	types.ERR_BLACKLISTED: lambda reason, contact, **_:
		em( "You've been blacklisted" + (reason and " for {reason!x}" or "") )+
		( em("\ncontact:") + " {contact}" if contact else "" ),
	types.ERR_ALREADY_UPVOTED: em("You have already upvoted this message."),
	types.ERR_UPVOTE_OWN_MESSAGE: em("You can't upvote your own message."),
	types.ERR_SPAMMY: em("Your message has not been sent. Avoid sending messages too fast, try again later."),
	types.ERR_SPAMMY_SIGN: em("Your message has not been sent. Avoid using /sign too often, try again later."),
	types.ERR_SIGN_PRIVACY: em("Your account privacy settings prevent usage of the sign feature. Enable linked forwards first."),
	types.ERR_INVALID_TRIP_FORMAT:
		em("Given tripcode is not valid, the format is ")+
		"<code>name#pass</code>" + em("."),
	types.ERR_NO_TRIPCODE: em("You don't have a tripcode set."),
	types.ERR_MEDIA_LIMIT: em("You can't send media or forward messages at this time, try again later."),

	types.USER_INFO: lambda warnings, cooldown, **_:
		"<b>id</b>: {id}, <b>username</b>: {username!x}, <b>rank</b>: {rank_i} ({rank})\n"+
		"<b>pats</b>: {karma}\n"+
		"<b>warnings</b>: {warnings} " + smiley(warnings)+
		( " (one warning will be removed on {warnExpiry!t})" if warnings > 0 else "" ) + ", "+
		"<b>cooldown</b>: "+
		( cooldown and "yes, until {cooldown!t}" or "no" ),
	types.USER_INFO_MOD: lambda warnings, cooldown, **_:
		"<b>id</b>: {id} (<b>rank</b>: {rank})\n"+
		"<b>pats</b>: {karma}\n"+
		"<b>joined</b>: {joined!t}\n"+
		"<b>warnings</b>: {warnings} " +
		(" (one warning will be removed on {warnExpiry!t})" if warnings > 0 else "")+"\n"+
		"<b>cooldown</b>: "+
		(cooldown and "yes, until {cooldown!t}" or "no" ),
	types.USERS_INFO: "<b>{active}</b> <i>active and</i> {inactive} <i>inactive users</i> (<i>total</i>: {total})",
	types.USERS_INFO_EXTENDED:
		"<b>{active}</b> <i>active</i>, {inactive} <i>inactive and</i> "+
		"{blacklisted} <i>blacklisted users</i> (<i>total</i>: {total})",

	types.PROGRAM_VERSION: "secretlounge-ng v{version} ~ https://github.com/sfan5/secretlounge-ng",
	types.HELP: lambda rank, **_:
		"\n<b><u>Important commands</u></b>\n"+
		"	"+em("/info") +            " - <i>Show info about you</i>\n"+
		"	"+em("/help") +            " - <i>Show available commands</i>\n"+
		"	"+em("/users") +           " - <i>Show number of users</i>\n"+
		"\n<b><u>Additional commands</u></b>\n"+
		"	"+em("/stop") +            " - <i>Leave the chat</i>\n"+
		"	"+em("/version") +         " - <i>Show bot version</i>\n"+
		"\n<b><u>Pat commands</u></b>\n"+
		"	"+em("+1") +       " (reply) - <i>Give a pat</i>\n"+
		"	"+em("-1") +       " (reply) - <i>Revoke a pat</i>\n"+
		(
			"\n<b><u>Mod commands</u></b>\n"+
			"	"+em("/info") +        " (reply) - <i>Show info about a user</i>\n"+
			"	"+em("/modsay TEXT") +        "  - <i>Post mod message</i>\n"+
			"	"+em("/warn") +        " (reply) - <i>Warn a user</i>\n"+
			"	"+em("/remove") +      " (reply) - <i>Delete a message</i>\n"+
			"	"+em("/removeall") +   " (reply) - <i>Delete all messages</i>\n"+
			"	"+em("/delete") +      " (reply) - <i>Delete a message and warn the user</i>\n"+
			"	"+em("/deleteall") +   " (reply) - <i>Delete all messages and warn the user</i>\n"
		if rank >= RANKS.mod else "")+
		(
			"\n<b><u>Admin commands</u></b>\n"+
			"	"+em("/adminsay TEXT") +          "  - <i>Post admin message</i>\n"+
			"	"+em("/motd TEXT") +              "  - <i>Define welcome message (HTML)</i>\n"+
			"	"+em("/uncooldown ID/USERNAME") + "  - <i>Remove cooldown from a user</i>\n"+
			"	"+em("/mod USERNAME") +           "  - <i>Promote a user to mod</i>\n"+
			"	"+em("/admin USERNAME") +         "  - <i>Promote a user to admin</i>\n"+
			"	"+em("/blacklist REASON") +       "  - <i>Blacklist a user and delete all messages</i>\n"
		if rank >= RANKS.admin else "")
}

localization = {}

def formatForTelegram(m):
	s = localization.get(m.type)
	if s is None:
		s = format_strs[m.type]
	if type(s).__name__ == "function":
		s = s(**m.kwargs)
	cls = localization.get("_FORMATTER_", CustomFormatter)
	return cls().format(s, **m.kwargs)
