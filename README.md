# Discord bot for FreshGRLC.NET

## Requirements

* Python 3.5+
* Pipenv
* Server running `garlicoind`

## Installation

Clone this repository and navigate to the cloned directory.

If you do not already have Pipenv installed, you can do so via pip with the
command `pip install pipenv`.

Run `pipenv --three install` to create a virtual environment and install this
project's dependencies.

Copy the `config.example.py` file to `config.py`

Update the `JSON_RPC_ADDRESS` value in `config.py` to point towards your
`garlicoind` JSON-RPC server.

## Usage

The bot requires two environment variables to be set:

1. `DISCORD_TOKEN` - Your secret bot token. You can get one from https://discordapp.com/developers/applications/me
2. `DISCORD_BLOCK_NOTIFICATION_CHANNEL_ID` - A channel ID that will reset the last block time every time a message is posted to it.

One way to set these is by copying the `.env.example` file to `.env` and
updating the values in the `.env` file.

Once that's done run the command:

    pipenv run python bot.py
