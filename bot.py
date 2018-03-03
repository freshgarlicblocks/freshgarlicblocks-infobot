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


class Bot(discord.Client):

    def __init__(self, reset_channel_id):
        super().__init__()
        self.timeLastBlock = datetime.datetime.now()
        self.reset_channel_id = reset_channel_id

    async def on_ready(self):
        await self.change_presence(game=discord.Game(name=DISCORD_PRESENCE))

    async def on_message(self, message):
        if message.channel.id == self.reset_channel_id:
            self.timeLastBlock = datetime.datetime.now()
            return
        if message.content.split(' ')[0] == '!info':
            words = '''```Block Height: [bHeight]
    Difficulty: [difficulty]
    Network Hashrate: [nHash] GH/s

    Pool Hashrate: [pHash] GH/s | [percentage]%
    Pool Workers: [workers]
    Pool Average Luck: [aLuck]%

    Time Since Last Block: [timeSince]```'''
            nHash = 1
            pHash = 1
            async with aiohttp.get('https://garli.co.in/api/getnetworkhashps') as r:
                if r.status == 200:
                    response = await r.text()
                    nHash = round(float(response)/1e9, 2)
                    words = words.replace('[nHash]', str(nHash))
            access = AuthServiceProxy(JSON_RPC_ADDRESS)
            blockChainInfo = access.getblockchaininfo()
            words = words.replace('[bHeight]', str(blockChainInfo['blocks']))
            words = words.replace('[difficulty]', str(round(blockChainInfo['difficulty'], 2)))
            async with aiohttp.get(FRESHGRLC_API_ADDRESS + '/poolstats/noheights') as r:
                if r.status == 200:
                    response = await r.json()
                    pHash = round(float(response['averageHashrate'])/1e9, 2)
                    words = words.replace('[pHash]', str(pHash))
                    words = words.replace('[workers]', str(response['workers']))
            words = words.replace('[percentage]', str(round(pHash/nHash * 100, 2)))
            async with aiohttp.get(FRESHGRLC_API_ADDRESS + '/luck') as r:
                if r.status == 200:
                    response = await r.json()
                    luckArray = []
                    for blocks in response:
                        luckArray.append(blocks['luck'])
                    aLuck = round(statistics.mean(luckArray)* 100, 2)
                    words = words.replace('[aLuck]', str(aLuck))
            d = datetime.datetime.now() - self.timeLastBlock
            dString = str(d)
            dString = dString[:dString.find('.')]
            words = words.replace('[timeSince]', dString)
            await self.send_message(message.channel, words)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    load_dotenv()
    channel_id = os.getenv('DISCORD_BLOCK_NOTIFICATION_CHANNEL_ID')
    token = os.getenv('DISCORD_TOKEN')

    bot = Bot(channel_id)
    bot.run(token)
