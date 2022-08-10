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
start - Join the chat (start receiving messages)
stop - Leave the chat (stop receiving messages)
help - show all available commands
users - Find out how many users are in the chat
info - Get info about your account
remove - delete a message [mod]
delete - delete and warn [mod]
```

### Update schedule
We are constantly improving and updating this bot. Due to recent copyright violations by other bot owners we are keeping future updates locked for an indefinite amount of time, however. After we have updated our own bots and when we think it's time to release the update for the public we upload the changes to the `master` branch of this repository.

If you expenrience problems or if you have suggestions for this bot please open a new issue, we will look into it. If you need the latest sources which are not public, yet, please contact us directly via GitHub or one of our bots.
