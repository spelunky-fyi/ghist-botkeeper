import random
import string
from typing import Optional
from urllib.parse import quote_plus

import discord
from discord import app_commands
from discord.ext import commands

from ghist.checks import not_support_channel


SPELUNKICON_URL = "https://spelunky.fyi/spelunkicons/{word}.png?v=3"

SIZE_MAP = {
    "smallest": 3,
    "small": 4,
    "smaller": 5,
    "bigger": 7,
    "big": 8,
}

BIGGEST_HEART_WORDS = [
    "qmT4K",
    "pqZYQ",
    "0u6QWm",
    "0vG8EB",
    "0U9bnV",
    "19FSLf",
    "1dFJos",
    "1DIyVH",
    "1UxSuO",
    "2EQ7Ay",
]


class Spelunkicon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="spelunkicon",
        description="Generate a spelunkicon based on your Discord ID (or another word).",
    )
    @app_commands.describe(
        size="Icon size.",
        random_word="Generate a random word.",
        pride="Pride variant (random size).",
        classic="Classic variant.",
        chaos="Chaos variant.",
        word="A specific word to use.",
    )
    @app_commands.choices(
        size=[
            app_commands.Choice(name="smallest", value="smallest"),
            app_commands.Choice(name="small", value="small"),
            app_commands.Choice(name="smaller", value="smaller"),
            app_commands.Choice(name="bigger", value="bigger"),
            app_commands.Choice(name="big", value="big"),
            app_commands.Choice(name="biggest", value="biggest"),
        ]
    )
    @app_commands.check(not_support_channel)
    async def spelunkicon(
        self,
        interaction: discord.Interaction,
        size: Optional[app_commands.Choice[str]] = None,
        random_word: bool = False,
        pride: bool = False,
        classic: bool = False,
        chaos: bool = False,
        word: Optional[str] = None,
    ):
        size_value = size.value if size else None
        biggest = size_value == "biggest"
        resolved_size = SIZE_MAP.get(size_value)

        if biggest and not pride:
            word = random.choice(BIGGEST_HEART_WORDS)
            resolved_size = 7
        elif random_word:
            word = "".join(random.choices(string.ascii_uppercase + string.digits, k=60))
        else:
            if not word:
                word = str(interaction.user.id)
            word = quote_plus(word)[:63]

        if not word:
            await interaction.response.send_message(
                "Must provide some input.", ephemeral=True
            )
            return

        if len(word) >= 64:
            await interaction.response.send_message(
                "Inputs must be less than 64 characters currently.", ephemeral=True
            )
            return

        url = SPELUNKICON_URL.format(word=word)

        if pride:
            generator = random.Random(word)
            resolved_size = generator.choice(range(3, 9))

        if resolved_size is not None:
            url += f"&size={resolved_size}"

        if pride:
            url += "&egg=pride"

        if classic:
            url += "&egg=classic"

        if chaos:
            url += "&misc=64"

        await interaction.response.send_message(url)
