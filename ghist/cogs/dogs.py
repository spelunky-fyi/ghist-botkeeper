import logging
from discord.ext import commands

from ghist.checks import DOGS_CHANNELS


class Dogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if str(message.channel.id) not in DOGS_CHANNELS:
            return
        await message.add_reaction("🐶")
        await message.add_reaction("🐕")
        await message.add_reaction("🐩")
