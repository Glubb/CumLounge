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
	"KARMA_VOTED_UP",
	"KARMA_VOTED_DOWN",
	"KARMA_NOTIFICATION",
	"TRIPCODE_INFO",
	"TRIPCODE_SET",

	"ERR_NO_ARG",
	"ERR_COMMAND_DISABLED",
	"ERR_NO_REPLY",
	"ERR_NOT_IN_CACHE",
	"ERR_NO_USER",
	"ERR_NO_USER_BY_ID",
	"ERR_ALREADY_WARNED",
	"ERR_INVALID_DURATION",
	"ERR_NOT_IN_COOLDOWN",
	"ERR_COOLDOWN",
	"ERR_BLACKLISTED",
	"ERR_ALREADY_VOTED_UP",
	"ERR_ALREADY_VOTED_DOWN",
	"ERR_VOTE_OWN_MESSAGE",
	"ERR_SPAMMY",
	"ERR_SPAMMY_SIGN",
	"ERR_SPAMMY_VOTE_UP",
	"ERR_SPAMMY_VOTE_DOWN",
	"ERR_SIGN_PRIVACY",
	"ERR_INVALID_TRIP_FORMAT",
	"ERR_NO_TRIPCODE",
	"ERR_MEDIA_LIMIT",
	"ERR_NO_CHANGELOG",
	"ERR_POLL_NOT_ANONYMOUS",
	"ERR_REG_CLOSED",
	"ERR_VOICE_AND_VIDEO_PRIVACY_RESTRICTION",

	"USER_INFO",
	"USER_INFO_MOD",
	"USERS_INFO",
	"USERS_INFO_EXTENDED",

	"PROGRAM_VERSION",
	"PROGRAM_CHANGELOG",
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
	types.SUCCESS_DELETE: "☑ <i>The message by</i> <b>{id}</b> <i>has been deleted</i>",
	types.SUCCESS_DELETEALL: "☑ <i>All</i> {count} <i>messages by</i> <b>{id}</b> <i>have been deleted</i>",
	types.SUCCESS_WARN_DELETE: "☑ <b>{id}</b> <i>has been warned and the message was deleted</i>",
	types.SUCCESS_WARN_DELETEALL: "☑ <b>{id}</b> <i>has been warned and all {count} messages were deleted</i>",
	types.SUCCESS_BLACKLIST: "☑ <b>{id}</b> <i>has been blacklisted and the message was deleted</i>",
	types.SUCCESS_BLACKLIST_DELETEALL: "☑ <b>{id}</b> <i>has been blacklisted and all {count} messages were deleted</i>",
	types.BOOLEAN_CONFIG: lambda enabled, **_:
		"<b>{description!x}</b>: " + (enabled and "enabled" or "disabled"),

	types.CHAT_JOIN: em("You joined the {bot_name} lounge!"),
	types.CHAT_LEAVE: em("You left the {bot_name} lounge!"),
	types.USER_IN_CHAT: em("You're already in the {bot_name} lounge."),
	types.USER_NOT_IN_CHAT: em("You're not in the {bot_name} lounge yet. Use /start to join!"),
	types.GIVEN_COOLDOWN: lambda deleted, **_:
		em( "You've been handed a cooldown of {duration!d} for this message. Please read the /rules!"+
			(deleted and " (message also deleted)" or "") ),
	types.MESSAGE_DELETED:
		em( "Your message has been deleted. No cooldown has been "
			"given this time, but refrain from posting it again." ),
	types.PROMOTED_MOD: em("You've been promoted to moderator, run /help for a list of commands."),
	types.PROMOTED_ADMIN: em("You've been promoted to admin, run /help for a list of commands."),
	types.KARMA_VOTED_UP: em("You just gave this {bot_name} a pat, awesome!"),
	types.KARMA_VOTED_DOWN: em("You just removed a pat from this {bot_name}!"),
	types.KARMA_NOTIFICATION: lambda count, **_:
		em( "You have just " + ("been given" if count > 0 else "lost") +" a pat! (check /info to see your pats"+
			" or /togglepats to turn these notifications off)" ),
	types.TRIPCODE_INFO: lambda tripcode, **_:
		"<b>tripcode</b>: " + ("<code>{tripcode!x}</code>" if tripcode is not None else "unset"),
	types.TRIPCODE_SET: em("Tripcode set. It will appear as: ") + "<b>{tripname!x}</b> <code>{tripcode!x}</code>",

	types.ERR_NO_ARG: em("This command requires an argument."),
	types.ERR_COMMAND_DISABLED: em("This command has been disabled."),
	types.ERR_NO_REPLY: em("You need to reply to a message to use this command."),
	types.ERR_NOT_IN_CACHE: em("Message not found in cache... (24h passed or bot was restarted)"),
	types.ERR_NO_USER: em("No user found by that name!"),
	types.ERR_NO_USER_BY_ID: em("No user found by that id! Note that all ids rotate every 24 hours."),
	types.ERR_COOLDOWN: em("Your cooldown expires at {until!t}"),
	types.ERR_ALREADY_WARNED: em("A warning has already been issued for this message."),
	types.ERR_INVALID_DURATION: em("You entered an invalid cooldown duration"),
	types.ERR_NOT_IN_COOLDOWN: em("This user is not in a cooldown right now."),
	types.ERR_BLACKLISTED: lambda reason, contact, **_:
		em( "You've been blacklisted" + (reason and " for {reason!x}" or "") )+
		( em("\ncontact:") + " {contact}" if contact else "" ),
	types.ERR_ALREADY_VOTED_UP: em("You have already given pats for this message"),
	types.ERR_ALREADY_VOTED_DOWN: em("You have already removed a pat for this message"),
	types.ERR_VOTE_OWN_MESSAGE: em("You cannot give or remove yourself pats"),
	types.ERR_SPAMMY: em("Your message has not been sent. Avoid sending messages too fast, try again later."),
	types.ERR_SPAMMY_SIGN: em("Your message has not been sent. Avoid using /sign too often, try again later."),
	types.ERR_SPAMMY_VOTE_UP:
		"<i>Your pat was not transmitted.\n" +
		"Avoid using +1 too often, try again later.</i>",
	types.ERR_SPAMMY_VOTE_DOWN:
		"<i>The pat was not removed.\n" +
		"Avoid using -1 too often, try again later</i>.",
	types.ERR_SIGN_PRIVACY: em("Your account privacy settings prevent usage of the sign feature. Enable linked forwards first."),
	types.ERR_INVALID_TRIP_FORMAT:
		em("Given tripcode is not valid, the format is ")+
		"<code>name#pass</code>" + em("."),
	types.ERR_NO_TRIPCODE: em("You don't have a tripcode set."),
	types.ERR_MEDIA_LIMIT: em("You can't send media or forward messages at this time, try again later."),
	types.ERR_NO_CHANGELOG: em("Changelog not found"),
	types.ERR_POLL_NOT_ANONYMOUS: em("Poll or quiz must be anonymous!"),
	types.ERR_REG_CLOSED: em("Registrations are closed"),
	types.ERR_VOICE_AND_VIDEO_PRIVACY_RESTRICTION: "<i>This message cannot be displayed on premium accounts with restricted access to voice or video messages</i>",

	types.USER_INFO: lambda warnings, cooldown, **_:
		"<b>id</b>: {id}, <b>username</b>: {username!x}, <b>rank</b>: {rank_i} ({rank})\n"+
		"<b>pats</b>: {karma}\n"+
		"<b>warnings</b>: {warnings} " + smiley(warnings)+
		( " (one warning will be removed on {warnExpiry!t})" if warnings > 0 else "" ) + ", "+
		"<b>cooldown</b>: "+
		( cooldown and "yes, until {cooldown!t}" or "no" ),
	types.USER_INFO_MOD: lambda warnings, cooldown, joined, **_:
		"<b>id</b>: {id} (<b>rank</b>: {rank})\n"+
		"<b>pats</b>: ~{karma}\n"+
		("<b>joined</b>: {joined!t}\n" if joined else "")+
		"<b>warnings</b>: {warnings} " +
		(" (one warning will be removed on {warnExpiry!t})" if warnings > 0 else "")+"\n"+
		"<b>cooldown</b>: "+
		(cooldown and "yes, until {cooldown!t}" or "no" ),
	types.USERS_INFO: "<b>{active}</b> <i>active and</i> {inactive} <i>inactive users</i> (<i>total</i>: {total})",
	types.USERS_INFO_EXTENDED:
		"<b>{active}</b> <i>active</i>, {inactive} <i>inactive and</i> "+
		"{blacklisted} <i>blacklisted users</i> (<i>total</i>: {total})",

	types.PROGRAM_VERSION: "<b>catlounge v{version}</b> <i>is a fork of the original secretloungebot. " +
		"View our changes and source code in @catloungeadmin</i>",
	types.PROGRAM_CHANGELOG: lambda versions, count=-1, **_:
		"\n\n".join(["<b><u>" + version + "</u></b>\n" +
			"\n".join(
				"• " + (
					"<b>%s:</b> %s" % (
						parts[0].strip(), ":".join(
							parts[slice(1, len(parts))]
						).strip()
					) if len(
						parts := change.split(":")
					) >= 2 else "%s" % change
				) for change in changes
			) for index, (version, changes) in enumerate(
				versions.items()
			) if (count < 0) or (index >= len(versions) - count)
		]),
	types.HELP: lambda rank, **_:
		"<b><u>Important commands</u></b>\n"+
		"	/start" +              " - <i>Join the chat</i>\n"+
		(
		"	/stop" +               " - <i>Leave the chat</i>\n"+
		"	/info" +               " - <i>Show info about you</i>\n"
		if rank is not None else "")+
		"	/help" +               " - <i>Show available commands</i>\n"+
		"\n<b><u>Additional commands</u></b>\n"+
		(
		"	/users" +              " - <i>Show number of users</i>\n"
		if rank is not None else "")+
		"	/version" +            " - <i>Show bot version</i>\n"+
		"	/changelog" +            " - <i>Show changelog</i>\n"+
		(
		"	/rules" +               " - <i>Show rules</i>\n"+
		"	/toggledebug" +        " - <i>Toggle debug message</i>\n"+
		"	/s TEXT" +             " - <i>Sign a message with your username</i>\n"
		if rank is not None else "")+
		(
		"\n<b><u>Pat commands</u></b>\n"+
		"	+1" +          " (reply) - <i>Give a pat</i>\n"+
		"	-1" +          " (reply) - <i>Remove a pat</i>\n"+
		"	/togglepats" +         " - <i>Toggle pat notifications</i>\n"+
		(
			"\n<b><u>Mod commands</u></b>\n"+
			"	/info" +                   " (reply) - <i>Show info about a user</i>\n"+
			"	/modsay TEXT" +            " - <i>Post mod message</i>\n"+
			"	/warn" +       	    " (reply) - <i>Warn a user</i>\n"+
			"	/remove" +      	    " (reply) - <i>Delete the message</i>\n"+
			"	/removeall" +   	    " (reply) - <i>Delete all messages from a user</i>\n"+
			"	/cooldown xs xm xh xd xw" +   " (reply) - <i>give a spicific cooldown+warn</i>\n"+
			"	/delete" +     	    " (reply) - <i>Warn a user and delete the message</i>\n"+
			"	/delete xs xm xh xd xw" +     " (reply) - <i>delete+warn and give a spicific cooldown</i>\n"+
			"	/deleteall" +              " (reply) - <i>Warn a user and delete all messages</i>\n"+
			"	/blacklist REASON" + " (reply) - <i>Blacklist a user and delete all messages</i>\n"
		if rank >= RANKS.mod else "")+
		(
			"\n<b><u>Admin commands</u></b>\n"+
			"	/adminsay TEXT" +            " - <i>Post admin message</i>\n"+
			"	/rules TEXT" +               " - <i>Define rules (HTML)</i>\n"+
			"	/uncooldown ID/USERNAME" +   " - <i>Remove cooldown from a user</i>\n"+
			"	/mod USERNAME" +             " - <i>Promote a user to mod</i>\n"+
			"	/admin USERNAME" +           " - <i>Promote a user to admin</i>\n"
		if rank >= RANKS.admin else "")
		if rank is not None else "")
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
