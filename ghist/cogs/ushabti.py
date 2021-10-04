import random

from discord.ext import commands

from ghist.checks import not_support_channel


TYPE_TO_ADJECTIVES = {
    "style": ["cracked", "tall", "smiling", "simple"],
    "material": ["clay", "gold", "jade", "wood", "onyx"],
    "symbol": ["eye", "ankh", "snake", "vortex", "bat"],
}


def invert_adjective_map(dict_):
    out = {}
    for type_, adjectives in dict_.items():
        for adjective in adjectives:
            out[adjective] = type_
    return out


ADJECTIVE_TO_TYPE = invert_adjective_map(TYPE_TO_ADJECTIVES)

USHABTI_URL = (
    "https://cdn.spelunky.fyi/static/images/ushabti/{style}-{material}-{symbol}.png"
)


class Ushabti(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        help="Display an ushabti.",
        brief="Display an ushabti.",
        usage="adjective [adjective] [adjective]",
    )
    @commands.check(not_support_channel)
    async def ushabti(self, ctx, adj1, adj2=None, adj3=None):
        adjectives = {
            "style": None,
            "material": None,
            "symbol": None,
        }

        for adj in [adj1, adj2, adj3]:
            if adj is None:
                continue
            type_ = ADJECTIVE_TO_TYPE.get(adj)
            if type_ is None:
                await ctx.send(f"Provided unknown value `{adj}`")
                return

            if adjectives[type_] is not None:
                await ctx.send(f"Provided more than one value of type {type_}")
                return

            adjectives[type_] = adj

        for type_, adj in adjectives.items():
            if adj is None:
                adjectives[type_] = random.choice(TYPE_TO_ADJECTIVES[type_])

        await ctx.send(USHABTI_URL.format(**adjectives))
