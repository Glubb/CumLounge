catlounge-ng-meow
---------------
Fork of [secretlounge-ng](https://github.com/secretlounge/secretlounge-ng), a bot to make an anonymous group chat on Telegram.

## Changelog

Version 0.1 
- /help shows now all available commands and detect if you are user/mod/admin.
- /adminhelp and /modhelp removed
- karma is now pats
- /togglekarma is now /togglepats
- extended user count is now visible for all users
- new mod command /deleteall and /removeall. It deletes all messages from the cache of the selected user
- /blacklist also deletes all messages from the cache of the selected user
- cooldown time has been increased
- admin /info shows now the real rank, karma value and join date

version 0.2
- you can now downvote with -1
- cooldown is 10 minutes for downvote another message

version 0.3
- /version and readme has been updated
- /motd is now /rules

## Setup
```
$ pip3 install -r requirements.txt
$ cp config.yaml.example config.yaml
Edit config.yaml with your favorite text editor.
$ ./secretlounge-ng
```

## @BotFather Setup
Message [@BotFather](https://t.me/BotFather) to configure your bot as follows:

* `/setprivacy`: enabled
* `/setjoingroups`: disabled
* `/setcommands`: paste the command list below

### Command list
```
help - show all available commands
start - Join the chat (start receiving messages)
stop - Leave the chat (stop receiving messages)
users - Find out how many users are in the chat
info - Get info about your account
sign - Sign a message with your username
s - Alias of sign
tsign - Sign a message with your tripcode
t - Alias of tsign
rules - Show the welcome message (rules)
version - Get version & source code of this bot
toggledebug - Toggle debug mode (sends back all messages to you)
togglepats - Toggle pat notifications
tripcode - Show or set a tripcode for your messages
```

## FAQ

1. **How do I unban a blacklisted user from my bot?**

To unban someone you need their Telegram User ID (preferred) or username/profile name.
If you have a name you can use `./util/blacklist.py find` to search your bot's database for the user record.

You can then run `./util/blacklist.py unban 12345678` to remove the ban.

2. **How do I demote somone I promoted to mod/admin at some point?**

If you already have an User ID in mind, proceed below.
Otherwise you can either use the find utility like explained above or run
`./util/perms.py list` to list all users with elevated rank.

Simply run `./util/perms.py set 12345678 user` to remove the users' privileges.

This can also be used to grant an user higher privileges by exchanging the last argument with "*mod*" or "*admin*".

3. **What is the suggested setup to run multiple bots?**

The `blacklist.py` and `perms.py` script, including advanced functions like blacklist syncing
(`./util/blacklist.py sync`), support a structure like the following where each bot
has its' own subdirectory:

```
root folder
\-- bot1
  \-- db.sqlite
  \-- config.yaml
\-- bot2
  \-- db.sqlite
  \-- ...
\-- ...
\-- README.md
\-- secretlounge-ng
```
