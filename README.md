# catlounge-ng-meow
Fork of [secretlounge-ng](https://github.com/secretlounge/secretlounge-ng), a bot to make an anonymous group chat on Telegram.

## Changes
You can find a general list of modifications in our sequencially-updated [changelog](changelog.txt) document.

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
