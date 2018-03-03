import discord
import aiohttp
import json
import asyncio
import shelve
from bitcoinrpc.authproxy import AuthServiceProxy
import datetime
from datetime import timedelta
import statistics
import pytz

client = discord.Client()

timeLastBlock = datetime.datetime.now(pytz.timezone("America/New_York"))

async def background():
    await client.wait_until_ready()
    await client.change_presence(game=discord.Game(name='Mining Simulator'))
    while not client.is_closed:
        await asyncio.sleep(120)

@client.event
async def on_message(message):
    if message.channel.id == '405494481513873420':
        global timeLastBlock
        timeLastBlock = datetime.datetime.now(pytz.timezone("America/New_York"))
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
                nHash = round(float(response)/1000000000, 2)
                words = words.replace('[nHash]', str(nHash))
        access = AuthServiceProxy("http://garlicoin:garlicoin@127.0.0.1:42070")
        blockChainInfo = access.getblockchaininfo()
        words = words.replace('[bHeight]', str(blockChainInfo['blocks']))
        words = words.replace('[difficulty]', str(round(blockChainInfo['difficulty'], 2)))
        async with aiohttp.get('https://www.freshgarlicblocks.net/api/poolstats/noheights') as r:
            if r.status == 200:
                response = await r.json()
                pHash = round(float(response['averageHashrate'])/1000000000, 2)
                words = words.replace('[pHash]', str(pHash))
                words = words.replace('[workers]', str(response['workers']))
        words = words.replace('[percentage]', str(round(pHash/nHash * 100, 2)))
        async with aiohttp.get('https://www.freshgrlc.net/api/luck') as r:
            if r.status == 200:
                response = await r.json()
                luckArray = []
                for blocks in response:
                    luckArray.append(blocks['luck'])
                aLuck = round(statistics.mean(luckArray)* 100, 2)
                words = words.replace('[aLuck]', str(aLuck))
        d = datetime.datetime.now(pytz.timezone("America/New_York")) - timeLastBlock
        dString = str(d)
        dString = dString[:dString.find('.')]
        words = words.replace('[timeSince]', dString)
        await client.send_message(message.channel, words)


client.loop.create_task(background())
client.run('secret')
