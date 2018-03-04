import datetime
import json
import logging
import re
import statistics
import os

import aiohttp
import asyncio
from bitcoinrpc.authproxy import AuthServiceProxy
import discord
from dotenv import load_dotenv

from config import *


INFO_MESSAGE_TEMPLATE = '''```Block Height: [block_height]
Difficulty: [difficulty]
Network Hashrate: [network_hashrate] GH/s

Pool Hashrate: [pool_hashrate] GH/s | [percentage]%
Pool Workers: [workers]
Pool Average Luck: [avg_luck]%

Time Since Last Block: [time_since]```'''


CMC_MESSAGE_TEMPLATE = '''**Rank:** [rank]
**Price:** $[price_usd] / [price_btc] BTC
**Market Cap:** $[market_cap_usd]
**Circulating Supply:** [available_supply] [symbol]
'''



class Bot(discord.Client):

    class RequestError(Exception):
        pass
        
    def __init__(self, reset_channel_id):
        super().__init__()
        self.time_last_block = datetime.datetime.now()
        self.reset_channel_id = reset_channel_id
        self.coin_icon_cache = {}

    async def on_ready(self):
        await self.change_presence(game=discord.Game(name=DISCORD_PRESENCE))

    async def on_message(self, message):
        split_msg = message.content.split(' ')

        if message.channel.id == self.reset_channel_id:
            self.time_last_block = datetime.datetime.now()
            return

        if split_msg[0] == '!info':
            words = INFO_MESSAGE_TEMPLATE
            network_hashrate = 1
            pool_hashrate = 1

            async with aiohttp.get('https://garli.co.in/api/getnetworkhashps') as r:
                if r.status == 200:
                    data = await r.text()
                    network_hashrate = round(float(data) / 1e9, 2)
                    words = words.replace('[network_hashrate]', str(network_hashrate))

            access = AuthServiceProxy(JSON_RPC_ADDRESS)
            blockchain_info = access.getblockchaininfo()
            words = words.replace('[block_height]', str(blockchain_info['blocks']))
            words = words.replace('[difficulty]', str(round(blockchain_info['difficulty'], 2)))

            async with aiohttp.get(FRESHGRLC_API_ADDRESS + '/poolstats/noheights') as r:
                if r.status == 200:
                    data = await r.json()
                    pool_hashrate = round(float(data['averageHashrate']) / 1e9, 2)
                    words = words.replace('[pool_hashrate]', str(pool_hashrate))
                    words = words.replace('[workers]', str(data['workers']))

            words = words.replace('[percentage]', str(round(pool_hashrate / network_hashrate * 100, 2)))

            async with aiohttp.get(FRESHGRLC_API_ADDRESS + '/luck') as r:
                if r.status == 200:
                    data = await r.json()
                    luck_array = []
                    for blocks in data:
                        luck_array.append(blocks['luck'])
                    avg_luck = round(statistics.mean(luck_array) * 100, 2)
                    words = words.replace('[avg_luck]', str(avg_luck))

            time_diff = datetime.datetime.now() - self.time_last_block
            time_since = str(time_diff)
            time_since = time_since[:time_since.find('.')]
            words = words.replace('[time_since]', time_since)

            await self.send_message(message.channel, words)
            return

        if split_msg[0] == '!cmc':
            coin_id = 'garlicoin'
            if len(split_msg) > 1 and split_msg[1].isalnum():
                coin_id = split_msg[1]

            msg = CMC_MESSAGE_TEMPLATE
            async with aiohttp.get('https://api.coinmarketcap.com/v1/ticker/%s/' % coin_id) as r:
                if r.status == 200:
                    data = await r.json()
                    coin = data[0]
                    for prop in coin:
                        msg = msg.replace('[%s]' % prop, str(coin[prop]))
                else:
                    raise self.RequestError('Error retreiving coin properties')
                    return

            coin_icon = await self.get_coin_icon(coin_id)
            if coin_icon is None:
                coin_icon = discord.Embed.Empty
            embed = discord.Embed()
            embed.set_author(
                name='%s | CoinMarketCap' % coin['name'],
                url=self.coin_url(coin_id),
                icon_url=coin_icon)
            embed.description = msg

            await self.send_message(message.channel, embed=embed)

    def coin_url(self, coin_id):
        return 'https://coinmarketcap.com/currencies/%s/' % coin_id

    async def get_coin_icon(self, coin_id):
        if not self.coin_icon_cache.get(coin_id):
            async with aiohttp.get(self.coin_url(coin_id)) as r:
                if r.status == 200:
                    html = await r.text()
                    # https://stackoverflow.com/a/1732454/69713
                    match = re.search(r'href="([^"]+/img/coins/32x32/[^"]+)"', html)
                    if match:
                        self.coin_icon_cache[coin_id] = match.group(1)
                else:
                    raise self.RequestError('Error retreiving coin icon')
        return self.coin_icon_cache.get(coin_id)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    load_dotenv()
    channel_id = os.getenv('DISCORD_BLOCK_NOTIFICATION_CHANNEL_ID')
    token = os.getenv('DISCORD_TOKEN')

    bot = Bot(channel_id)
    bot.run(token)
