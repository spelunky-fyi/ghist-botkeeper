import argparse
import asyncio
import json
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import aiohttp
import discord
from discord.ext import commands, tasks


TOKEN = os.environ["GHIST_BOT_TOKEN"]
MR_SYNC_KEY = os.environ["MR_SYNC_KEY"]
COLOR_PREFIX = "Color: "
PRONOUNS_PREFIX = "Pronouns: "


# Mapping of guild to list of channels where the bot will respond.
# If guild not found or channel list is empty then the bot will
# respond in all channels.
VALID_CHANNELS = defaultdict(list)

MR_SYNC_ENDPOINT = "https://mossranking.com/api/getdiscordusers.php"
GAMES_RE = re.compile(r"^games\[([A-Za-z0-9 ]+)\]$")


@dataclass
class MossRecord:
    """Represents a record from the Mossranking getdiscordusers endpoint.

    Example Payload:
    [
      {
        "mossranking[id_user]":"1",
        "mossranking[username]":"somename",
        "discord[id]":"6666666666666666",
        "discord[username]":"somediscordname",
        "games[Spelunky Classic]":true,
        "games[Spelunky HD]":true,
        "games[Spelunky 2]":true,
        "games[Roguelike Challenges]":true
      }
    ]
    """

    mossranking_id: int
    mossranking_username: str
    discord_id: int
    discord_username: str
    games: Dict[str, bool]

    @classmethod
    def from_dict(cls, data):
        games = {}

        for key, value in data.items():
            match = GAMES_RE.match(key)
            if match:
                games[match.group(1)] = value

        return cls(
            mossranking_id=int(data.get("mossranking[id_user]", 0)),
            mossranking_username=data.get("mossranking[username]", ""),
            discord_id=int(data.get("discord[id]", 0)),
            discord_username=data.get("discord[username]", ""),
            games=games,
        )


class MossrankingSync(commands.Cog):
    def __init__(self, bot, guild_id, role_id, game_role_ids):
        self.bot = bot
        self.guild_id = guild_id
        self.role_id = role_id
        self.game_role_ids = game_role_ids

        self.syncer.start()  # pylint: disable=no-member

    async def get_mr_discord_users(self):
        records = {}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                MR_SYNC_ENDPOINT, params={"key": MR_SYNC_KEY}
            ) as req:
                if req.status != 200:
                    return
                data = await req.json()

        for user in data:
            record = MossRecord.from_dict(user)
            if not record.discord_id:
                continue
            records[record.discord_id] = record

        return records

    def get_games_roles(self, guild):
        roles = {}
        for game, role_id in self.game_role_ids.items():
            role = guild.get_role(role_id)
            if role is None:
                continue
            roles[game] = role
        return roles

    @tasks.loop(seconds=1800.0)
    async def syncer(self):
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return

        role = guild.get_role(self.role_id)
        if not role:
            return

        game_roles = self.get_games_roles(guild)

        mr_records_by_did = await self.get_mr_discord_users()
        # Safety check in case api returns empty data
        if not mr_records_by_did:
            return

        for member in guild.members:
            to_add = []
            to_remove = []
            mr_record = mr_records_by_did.get(member.id)

            if mr_record:
                if role not in member.roles:
                    logging.info("Adding role %s to user %s", role.name, member.name)
                    to_add.append(role)
            else:
                if role in member.roles:
                    logging.info(
                        "Removing role %s from user %s", role.name, member.name
                    )
                    to_remove.append(role)

            for game, game_role in game_roles.items():
                if mr_record:
                    game_value = mr_record.games.get(game, False)
                    if game_value and game_role not in member.roles:
                        logging.info(
                            "Adding role %s to user %s", game_role.name, member.name
                        )
                        to_add.append(game_role)
                    elif not game_value and game_role in member.roles:
                        logging.info(
                            "Removing role %s from user %s", game_role.name, member.name
                        )
                        to_remove.append(game_role)
                else:
                    if game_role in member.roles:
                        logging.info(
                            "Removing role %s from user %s", game_role.name, member.name
                        )
                        to_remove.append(game_role)

            if to_add:
                await member.add_roles(*to_add)

            if to_remove:
                await member.remove_roles(*to_remove)

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


class Pronouns(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def get_pronouns_roles(roles):
        pronouns = {}
        for role in roles:
            if role.name.startswith(PRONOUNS_PREFIX):
                pronouns[role.name[len(PRONOUNS_PREFIX) :].lower()] = role
        return pronouns

    def get_guild_pronouns(self, ctx):
        return self.get_pronouns_roles(ctx.guild.roles)

    def get_author_pronouns(self, ctx):
        return self.get_pronouns_roles(ctx.author.roles)

    @commands.command(
        help="Set the pronouns you prefer.",
        brief="Set the prnouns you prefer.",
        usage="pronouns",
    )
    async def pronouns(self, ctx, *args):
        available_pronouns = self.get_guild_pronouns(ctx)
        # Check that the user passed pronouns at all
        if not args:
            await ctx.send(
                "Available pronouns: {}".format(
                    ", ".join(f"`{pronoun}`" for pronoun in available_pronouns)
                )
            )
            return

        requested_pronouns = [arg.strip().lower() for arg in args]
        target_pronouns = []
        unavailable_pronouns = []

        # Check that the requested pronouns are available.
        for pronouns in requested_pronouns:
            target = available_pronouns.get(pronouns)
            if target is None:
                unavailable_pronouns.append(pronouns)
            else:
                target_pronouns.append(target)

        if unavailable_pronouns:
            pronouns = ", ".join(f"`{pronoun}`" for pronoun in unavailable_pronouns)
            await ctx.send(
                "You've specified an unavailable pronoun. If you think this pronoun "
                "should be available please message a moderator to get it added. "
                "Available pronouns are: {}".format(
                    ", ".join(f"`{pronoun}`" for pronoun in available_pronouns)
                )
            )
            return

        # Give requested pronoun roles.
        await ctx.author.add_roles(*target_pronouns)

        # Remove any pronoun roles that weren't specified.
        roles_to_remove = set(self.get_author_pronouns(ctx).values())
        roles_to_remove.difference_update(target_pronouns)
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
    ghist.add_cog(Pronouns(ghist))

    if config.get("mr-sync"):
        ghist.add_cog(
            MossrankingSync(
                bot=ghist,
                guild_id=config["mr-sync"]["guild-id"],
                role_id=config["mr-sync"]["role-id"],
                game_role_ids=config["mr-sync"].get("games", {}),
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