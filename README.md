# catlounge-ng-meow
Fork of [secretlounge-ng](https://github.com/secretlounge/secretlounge-ng), a bot to make an anonymous group chat on Telegram.

## Changes
You can find a general list of modifications in our sequencially-updated [changelog](changelog.txt) document. This however only includes a selection of the most fundamental changes without much detail. Please see our [commit history](..\..\compare) for more detailed information on what has been changed.

From within the bot, you can access a prettified version of the changelog file with the `/changelog` command. It lists the changes of the past three releases by default.

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
start - Join the chat (start receiving messages)
stop - Leave the chat (stop receiving messages)
help - show all available commands
users - Find out how many users are in the chat
info - Get info about your account
remove - delete a message [mod]
delete - delete and warn [mod]
```
