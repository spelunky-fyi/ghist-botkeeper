import argparse
import asyncio
import aiohttp
import json
import logging
import os
from collections import defaultdict
from pathlib import Path

import discord
from discord.ext import commands, tasks

TOKEN = os.environ["GHIST_BOT_TOKEN"]
MR_SYNC_KEY = os.environ["MR_SYNC_KEY"]
COLOR_PREFIX = "Color: "

# Mapping of guild to list of channels where the bot will respond.
# If guild not found or channel list is empty then the bot will
# respond in all channels.
VALID_CHANNELS = defaultdict(list)

MR_SYNC_ENDPOINT = "https://mossranking.com/api/getdiscordusers.php"


class MossrankingSync(commands.Cog):
    def __init__(self, bot, guild_id, role_id):
        self.bot = bot
        self.guild_id = guild_id
        self.role_id = role_id
        self.syncer.start()  # pylint: disable=no-member

    async def get_mr_discord_users(self):
        user_ids = set()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                MR_SYNC_ENDPOINT, params={"key": MR_SYNC_KEY}
            ) as req:
                if req.status != 200:
                    return
                data = await req.json()
        for user in data:
            user_ids.add(int(user["discord[id]"]))

        return user_ids

    @tasks.loop(seconds=60.0)
    async def syncer(self):
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return

        role = guild.get_role(self.role_id)
        if not role:
            return

        mr_discord_ids = await self.get_mr_discord_users()
        # Safety check in case api returns empty data
        if not mr_discord_ids:
            return

        for member in guild.members:
            if member.id in mr_discord_ids:
                if role not in member.roles:
                    logging.info("Added role %s to user %s", role.name, member.name)
                    await member.add_roles(role)
            else:
                if role in member.roles:
                    logging.info("Removed role %s from user %s", role.name, member.name)
                    await member.remove_roles(role)

    @syncer.before_loop
    async def before_syncer(self):
        logging.info("Waiting for bot to be reading before starting sync task...")
        await self.bot.wait_until_ready()


class Color(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def get_colors_roles(roles):
        colors = {}
        for role in roles:
            if role.name.startswith(COLOR_PREFIX):
                colors[role.name[len(COLOR_PREFIX) :].lower()] = role
        return colors

    def get_guild_colors(self, ctx):
        return self.get_colors_roles(ctx.guild.roles)

    def get_author_colors(self, ctx):
        return self.get_colors_roles(ctx.author.roles)

    @commands.command(
        help="Set the color of your name.",
        brief="Set the color of your name.",
        usage="color_name",
    )
    async def color(self, ctx, *args):
        # Check that the user passed a color at all
        if not args:
            await ctx.send("See pins for available colors.")
            return

        requested_color = " ".join(args).strip().lower()
        guild_color_roles = self.get_guild_colors(ctx)

        # Check that the requested color is available.
        target_role = guild_color_roles.get(requested_color)
        if target_role is None:
            await ctx.send(
                f"The color `{requested_color}` isn't available. See pins for available colors."
            )
            return

        # Give requested color role. We add the color first as small
        # UI benefit so we don't see the color flash back to default color
        # when changing colors.
        await ctx.author.add_roles(target_role)

        # Remove other color roles
        roles_to_remove = set(self.get_author_colors(ctx).values())
        roles_to_remove.discard(target_role)
        if roles_to_remove:
            await ctx.author.remove_roles(*roles_to_remove)

        await ctx.message.add_reaction("👍")


async def globally_block_dms(ctx):
    return ctx.guild is not None


async def check_valid_channels(ctx):
    if ctx.guild is None:
        return False

    channels = VALID_CHANNELS.get(str(ctx.guild.id))
    if not channels:
        return True

    return str(ctx.message.channel.id) in channels


def parse_config(config_path):
    with config_path.open("r") as config_file:
        data = json.load(config_file)

    for guild, channels in data.get("valid-channels", {}).items():
        VALID_CHANNELS[guild] = channels

    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prefix", default="!", help="The prefix this bot uses on bot commands."
    )
    parser.add_argument(
        "--config",
        default=Path(__file__).absolute().parent / "ghist-bot-config.json",
        type=Path,
        help="Path to config file.",
    )
    args = parser.parse_args()

    config = {}
    if args.config.exists():
        config = parse_config(args.config)

    # Change only the no_category default string
    help_command = commands.DefaultHelpCommand(no_category="Commands")

    intents = discord.Intents.default()
    intents.members = True

    ghist = commands.Bot(
        command_prefix=args.prefix, help_command=help_command, intents=intents
    )

    # Cog Setup
    ghist.add_cog(Color(ghist))

    if config.get("mr-sync"):
        ghist.add_cog(
            MossrankingSync(
                bot=ghist,
                guild_id=config["mr-sync"]["guild-id"],
                role_id=config["mr-sync"]["role-id"],
            )
        )

    # Global Checks
    ghist.add_check(globally_block_dms)
    ghist.add_check(check_valid_channels)

    ghist.run(TOKEN)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    main()
