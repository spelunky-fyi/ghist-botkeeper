import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


STYLES = ["cracked", "tall", "smiling", "simple"]
MATERIALS = ["clay", "gold", "jade", "wood", "onyx"]
SYMBOLS = ["eye", "ankh", "snake", "vortex", "bat"]

USHABTI_URL = (
    "https://cdn.spelunky.fyi/static/images/ushabti/{style}-{material}-{symbol}.png"
)


class Ushabti(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="ushabti",
        description="Display an ushabti. Any unspecified slots are picked at random.",
    )
    @app_commands.describe(
        style="The ushabti's style.",
        material="The ushabti's material.",
        symbol="The ushabti's symbol.",
    )
    @app_commands.choices(
        style=[app_commands.Choice(name=s, value=s) for s in STYLES],
        material=[app_commands.Choice(name=m, value=m) for m in MATERIALS],
        symbol=[app_commands.Choice(name=s, value=s) for s in SYMBOLS],
    )
    async def ushabti(
        self,
        interaction: discord.Interaction,
        style: Optional[app_commands.Choice[str]] = None,
        material: Optional[app_commands.Choice[str]] = None,
        symbol: Optional[app_commands.Choice[str]] = None,
    ):
        style_value = style.value if style else random.choice(STYLES)
        material_value = material.value if material else random.choice(MATERIALS)
        symbol_value = symbol.value if symbol else random.choice(SYMBOLS)

        url = USHABTI_URL.format(
            style=style_value, material=material_value, symbol=symbol_value
        )
        await interaction.response.send_message(url, ephemeral=True)
