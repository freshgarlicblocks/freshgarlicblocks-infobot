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


client = discord.Client()


@client.event
async def on_ready():
    await client.change_presence(game=discord.Game(name=DISCORD_PRESENCE))


@client.event
async def on_message(message):
    if message.channel.id == DISCORD_BLOCK_NOTIFICATION_CHANNEL_ID:
        global timeLastBlock
        timeLastBlock = datetime.datetime.now()
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
        d = datetime.datetime.now() - timeLastBlock
        dString = str(d)
        dString = dString[:dString.find('.')]
        words = words.replace('[timeSince]', dString)
        await client.send_message(message.channel, words)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    load_dotenv()
    DISCORD_BLOCK_NOTIFICATION_CHANNEL_ID=os.getenv('DISCORD_BLOCK_NOTIFICATION_CHANNEL_ID')
    DISCORD_TOKEN=os.getenv('DISCORD_TOKEN')

    timeLastBlock = datetime.datetime.now()

    client.run(DISCORD_TOKEN)
