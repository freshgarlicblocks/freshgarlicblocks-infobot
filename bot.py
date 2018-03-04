import datetime
import json
import logging
import re
import statistics
import os
import shelve

import aiohttp
import asyncio
from bitcoinrpc.authproxy import AuthServiceProxy
import discord
from dotenv import load_dotenv

from config import *


INFO_MESSAGE_TEMPLATE = '''Block Height: [block_height]
Difficulty: [difficulty]
Network Hashrate: [network_hashrate] GH/s

Pool Hashrate: [pool_hashrate] GH/s | [percentage]%
Pool Workers: [workers]
Pool Average Luck: [avg_luck]%

Time Since Last Block: [time_since]'''


CMC_MESSAGE_TEMPLATE = '''**Rank:** [rank]
**Price:** $[price_usd] / [price_btc] BTC
**Market Cap:** $[market_cap_usd]
**Circulating Supply:** [available_supply] [symbol]'''

WORKER_INFO_MESSAGE_TEMPLATE = '''Address: [address]

Expected Payout per Block: [expected_payout] GRLC
Estimated Hashrate: [worker_hashrate] MH/s
Percentage of Pool: [worker_percentage]%'''

ADDRESS_SET_ERROR_MESSAGE = '''Error, your address is not set!

Please set it with: `!register <address>`'''

class Bot(discord.Client):

    class RequestError(Exception):
        pass

    def __init__(self, reset_channel_id):
        super().__init__()
        self.time_last_block = datetime.datetime.now()
        self.reset_channel_id = reset_channel_id
        self.coin_icon_cache = {}

        loop_break = 0
        while loop_break < 2:
            loop_break += 1
            db_shelve = shelve.open('db')
            try:
                self.users = db_shelve['users']
                db_shelve.close()
                break
            except KeyError:
                db_shelve['users'] = {}
                db_shelve.close()
                continue


    async def on_ready(self):
        await self.change_presence(game=discord.Game(name=DISCORD_PRESENCE))

    async def on_message(self, message):
        split_msg = message.content.split(' ')

        if message.channel.id == self.reset_channel_id:
            self.time_last_block = datetime.datetime.now()
            return

        if split_msg[0] == '!info':
            msg = INFO_MESSAGE_TEMPLATE
            network_hashrate = 1
            pool_hashrate = 1

            async with aiohttp.get('https://garli.co.in/api/getnetworkhashps') as r:
                if r.status == 200:
                    data = await r.text()
                    network_hashrate = round(float(data) / 1e9, 2)
                    msg = msg.replace('[network_hashrate]', str(network_hashrate))

                else:
                    self.RequestError('Error retreiving network hashrate')
                    return

            access = AuthServiceProxy(JSON_RPC_ADDRESS)
            blockchain_info = access.getblockchaininfo()
            msg = msg.replace('[block_height]', str(blockchain_info['blocks']))
            msg = msg.replace('[difficulty]', str(round(blockchain_info['difficulty'], 2)))

            async with aiohttp.get(FRESHGRLC_API_ADDRESS + '/poolstats/noheights') as r:
                if r.status == 200:
                    data = await r.json()
                    pool_hashrate = round(float(data['averageHashrate']) / 1e9, 2)
                    msg = msg.replace('[pool_hashrate]', str(pool_hashrate))
                    msg = msg.replace('[workers]', str(data['workers']))

                else:
                    self.RequestError('Error retreiving pool pool hashrate and worker count')
                    return

            msg = msg.replace('[percentage]', str(round(pool_hashrate / network_hashrate * 100, 2)))

            async with aiohttp.get(FRESHGRLC_API_ADDRESS + '/luck') as r:
                if r.status == 200:
                    data = await r.json()
                    luck_array = []
                    for blocks in data:
                        luck_array.append(blocks['luck'])
                    avg_luck = round(statistics.mean(luck_array) * 100, 2)
                    msg = msg.replace('[avg_luck]', str(avg_luck))

                else:
                    self.RequestError('Error retreiving pool pool luck')
                    return

            time_diff = datetime.datetime.now() - self.time_last_block
            time_since = str(time_diff)
            time_since = time_since[:time_since.find('.')]
            msg = msg.replace('[time_since]', time_since)

            embed = discord.Embed()
            embed.set_author(
                name='Fresh Garlic Blocks Info')
            embed.description = msg
            embed.color = discord.Color(0xffa517)

            await self.send_message(message.channel, embed=embed)
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
            embed.color = discord.Color(0xffa517)

            await self.send_message(message.channel, embed=embed)
            return

        if split_msg[0] == '!myinfo':
            msg = WORKER_INFO_MESSAGE_TEMPLATE
            try:
                user = self.users[str(message.author)]
                msg = msg.replace('[address]', user['address'])
                async with aiohttp.get(FRESHGRLC_API_ADDRESS + '/workerinfo/' + user['address']) as r:
                    if r.status == 200:
                        data = await r.json()
                        expected_payout = data['nextpayout']['grlc']
                        worker_hashrate = round(float(data['hashrate']) / 1e6, 2)
                        worker_percentage = round(data['nextpayout']['percentage'], 2)
                        msg = msg.replace('[expected_payout]', str(expected_payout))
                        msg = msg.replace('[worker_hashrate]', str(worker_hashrate))
                        msg = msg.replace('[worker_percentage]', str(worker_percentage))

                    elif r.status == 500:
                        msg = 'Error, your address is not currently mining!'

                    else:
                        self.RequestError('Error retreiving worker information')
                        return

            except KeyError:
                msg = ADDRESS_SET_ERROR_MESSAGE

            embed = discord.Embed()
            embed.set_author(
                name=message.author.display_name + "'s Info")
            embed.description = msg
            embed.color = discord.Color(0xffa517)

            await self.send_message(message.channel, embed=embed)
            return

        if split_msg[0] == '!register':
            address = 'invalid'
            access = AuthServiceProxy(JSON_RPC_ADDRESS)
            if len(split_msg) > 1 and access.validateaddress(split_msg[1])['isvalid']:
                address = split_msg[1]
                self.users[str(message.author)] = {'address': address}

                db_shelve = shelve.open('db')
                db_shelve['users'] = self.users
                db_shelve.close()

                embed = discord.Embed()
                embed.set_author(
                    name=message.author.display_name + ' Registered')
                embed.description = 'You are now registered! Use`!myinfo` to see information about yourself!'
                embed.color = discord.Color(0xffa517)

                await self.send_message(message.channel, embed=embed)
                return

    def coin_url(self, coin_id):
        return 'https://coinmarketcap.com/currencies/%s/' % coin_id

    async def get_coin_icon(self, coin_id):
        if not self.coin_icon_cache.get(coin_id):
            async with aiohttp.get(self.coin_url(coin_id)) as r:
                if r.status == 200:
                    html = await r.text()
                    # see https://stackoverflow.com/a/1732454/69713
                    match = re.search(r'href="([^"]+/img/coins/32x32/[^"]+)"', html)
                    if match:
                        self.coin_icon_cache[coin_id] = match.group(1)
                else:
                    raise self.RequestError('Error retreiving coin icon')
                    return

        return self.coin_icon_cache.get(coin_id)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    load_dotenv()
    channel_id = os.getenv('DISCORD_BLOCK_NOTIFICATION_CHANNEL_ID')
    token = os.getenv('DISCORD_TOKEN')

    bot = Bot(channel_id)
    bot.run(token)
