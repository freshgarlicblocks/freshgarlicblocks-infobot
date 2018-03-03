import datetime
import json
import logging
import statistics
import os

import aiohttp
import asyncio
from bitcoinrpc.authproxy import AuthServiceProxy
import discord
from dotenv import load_dotenv

from config import *


MESSAGE_TEMPLATE = '''```Block Height: [b_height]
Difficulty: [difficulty]
Network Hashrate: [n_hash] GH/s

Pool Hashrate: [p_hash] GH/s | [percentage]%
Pool Workers: [workers]
Pool Average Luck: [a_luck]%

Time Since Last Block: [time_since]```'''


class Bot(discord.Client):

    def __init__(self, reset_channel_id):
        super().__init__()
        self.time_last_block = datetime.datetime.now()
        self.reset_channel_id = reset_channel_id

    async def on_ready(self):
        await self.change_presence(game=discord.Game(name=DISCORD_PRESENCE))

    async def on_message(self, message):
        if message.channel.id == self.reset_channel_id:
            self.time_last_block = datetime.datetime.now()
            return

        if message.content.split(' ')[0] == '!info':
            words = MESSAGE_TEMPLATE
            n_hash = 1
            p_hash = 1

            async with aiohttp.get('https://garli.co.in/api/getnetworkhashps') as r:
                if r.status == 200:
                    response = await r.text()
                    n_hash = round(float(response) / 1e9, 2)
                    words = words.replace('[n_hash]', str(n_hash))

            access = AuthServiceProxy(JSON_RPC_ADDRESS)
            blockchain_info = access.getblockchaininfo()
            words = words.replace('[b_height]', str(blockchain_info['blocks']))
            words = words.replace('[difficulty]', str(round(blockchain_info['difficulty'], 2)))

            async with aiohttp.get(FRESHGRLC_API_ADDRESS + '/poolstats/noheights') as r:
                if r.status == 200:
                    response = await r.json()
                    p_hash = round(float(response['averageHashrate']) / 1e9, 2)
                    words = words.replace('[p_hash]', str(p_hash))
                    words = words.replace('[workers]', str(response['workers']))

            words = words.replace('[percentage]', str(round(p_hash / n_hash * 100, 2)))

            async with aiohttp.get(FRESHGRLC_API_ADDRESS + '/luck') as r:
                if r.status == 200:
                    response = await r.json()
                    luck_array = []
                    for blocks in response:
                        luck_array.append(blocks['luck'])
                    a_luck = round(statistics.mean(luck_array) * 100, 2)
                    words = words.replace('[a_luck]', str(a_luck))

            d = datetime.datetime.now() - self.time_last_block
            d_string = str(d)
            d_string = d_string[:d_string.find('.')]
            words = words.replace('[time_since]', d_string)

            await self.send_message(message.channel, words)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    load_dotenv()
    channel_id = os.getenv('DISCORD_BLOCK_NOTIFICATION_CHANNEL_ID')
    token = os.getenv('DISCORD_TOKEN')

    bot = Bot(channel_id)
    bot.run(token)
