import random
import string
from urllib.parse import quote_plus

from discord.ext import commands

from ghist.checks import not_support_channel


SPELUNKICON_URL = "https://spelunky.fyi/spelunkicons/{word}.png?v=3"


class Spelunkicon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        help="Generate a spelunkicon based on your Discord ID (or another word).",
        brief="Generate a spelunkicon.",
        usage="[!big|!bigger|!smaller|!small|!smallest] [!random] [!pride] [!classic] [!chaos] [word]",
    )
    @commands.check(not_support_channel)
    async def spelunkicon(self, ctx, *, orig_words=None):
        size = None
        gen_random = False
        pride = False
        classic = False
        random_size = False

        words = []
        if orig_words:
            orig_words = orig_words.split()
            for word in orig_words:
                if word == "!big":
                    size = 8
                elif word == "!bigger":
                    size = 7
                elif word == "!smaller":
                    size = 5
                elif word == "!small":
                    size = 4
                elif word == "!smallest":
                    size = 3
                elif word == "!random":
                    gen_random = True
                elif word == "!pride":
                    pride = True
                    random_size = True
                elif word == "!classic":
                    classic = True
                else:
                    words.append(word)

        if gen_random:
            word = "".join(random.choices(string.ascii_uppercase + string.digits, k=60))
        else:
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
        if random_size:
            generator = random.Random(word)
            size = generator.choice(range(3, 9))

        if size is not None:
            url += f"&size={size}"

        if pride:
            url += "&egg=pride"

        if classic:
            url += "&egg=classic"

        if chaos:
            url += "&misc=64"

        await ctx.send(url)
