from urllib.parse import quote_plus

from discord.ext import commands

from ghist.checks import not_support_channel


SPELUNKICON_URL = "https://spelunky.fyi/spelunkicons/{word}.png"


class Spelunkicon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        help="Generate a spelunkicon based on your Discord ID (or another word).",
        brief="Generate a spelunkicon.",
        usage="[word]",
    )
    @commands.check(not_support_channel)
    async def spelunkicon(self, ctx, word=None):
        if word is None:
            word = str(ctx.author.id)

        word = quote_plus(word)

        if not word:
            await ctx.send(f"Must provide some input.")
            return

        if len(word) >= 64:
            await ctx.send(f"Inputs must be less than 64 characters currently.")
            return

        await ctx.send(SPELUNKICON_URL.format(word=word))
