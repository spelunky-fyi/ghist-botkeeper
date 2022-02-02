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
        usage="[!big|!small] [word]",
    )
    @commands.check(not_support_channel)
    async def spelunkicon(self, ctx, *words):
        big = False
        small = False
        if words:
            if words[0] == "!big":
                words = words[1:]
                big = True
            elif words[0] == "!small":
                words = words[1:]
                small = True

        if not words:
            word = str(ctx.author.id)
        else:
            word = " ".join(words)

        word = quote_plus(word)[:63]

        if not word:
            await ctx.send(f"Must provide some input.")
            return

        if len(word) >= 64:
            await ctx.send(f"Inputs must be less than 64 characters currently.")
            return

        url = SPELUNKICON_URL.format(word=word)
        if big:
            url += "?size=8"
        elif small:
            url += "?size=4"

        await ctx.send(url)
