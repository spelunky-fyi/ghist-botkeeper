import argparse
import colorsys
import json
import logging
import os
import io
import re
import random
import datetime
from collections import defaultdict
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Dict

import aiohttp
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from ttf_opensans import opensans
from PIL import Image, ImageDraw


load_dotenv("ghist-bot.env")
TOKEN = os.environ["GHIST_BOT_TOKEN"]
MR_SYNC_KEY = os.environ["MR_SYNC_KEY"]
COLOR_PREFIX = "Color: "
PRONOUNS_PREFIX = "Pronouns: "

IMG_FONT = opensans(font_weight=600).imagefont(size=16)
FONT_X_PADDING = 5
FONT_Y_PADDING = 5


def chunk(items, num_chunks=3):
    chunks = []

    if not items:
        return chunks

    chunk_size = ceil(len(items) / num_chunks)
    for idx in range(0, len(items), chunk_size):
        chunks.append(items[idx : idx + chunk_size])

    return chunks


def get_text_color(rgb):
    if (rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114) > 160:
        return (0, 0, 0, 255)
    return (255, 255, 255, 255)


def make_available_colors_image(roles):

    max_column_widths = []
    max_text_height = 0

    roles = [
        (k, v)
        for k, v in sorted(
            roles.items(),
            key=lambda role: colorsys.rgb_to_hsv(*role[1].color.to_rgb())
        )
    ]
    roles = chunk(roles, 3)

    for column_idx, column in enumerate(roles):
        for role_name, _ in column:
            if len(max_column_widths) == column_idx:
                max_column_widths.append(0)

            width, height = IMG_FONT.getsize(role_name, None, None, None, 0)
            max_text_height = max(max_text_height, height)
            max_column_widths[column_idx] = max(max_column_widths[column_idx], width)

    img_width = sum(max_column_widths) + ((len(roles) * 2) * FONT_X_PADDING)
    max_len_column = max(map(len, roles))
    img_height = (max_len_column * max_text_height) + (
        (max_len_column * 2) * FONT_Y_PADDING
    )

    out_img = Image.new("RGBA", (img_width, img_height))
    img_draw = ImageDraw.Draw(out_img)

    x0 = 0
    for column_idx, column in enumerate(roles):
        column_width = max_column_widths[column_idx] + FONT_X_PADDING * 2
        for row_idx, (role_name, role) in enumerate(column):
            row_height = max_text_height + FONT_Y_PADDING * 2
            x1 = x0 + column_width - 1
            y0 = row_idx * row_height
            y1 = y0 + row_height - 1
            img_draw.rectangle([x0, y0, x1, y1], fill=role.color.to_rgb())
            img_draw.text(
                (x0 + FONT_X_PADDING, y0 + FONT_Y_PADDING),
                role_name,
                font=IMG_FONT,
                fill=get_text_color(role.color.to_rgb()),
            )

        x0 += column_width

    buf = io.BytesIO()
    out_img.save(buf, format="PNG")
    buf.seek(0)

    return buf


# Mapping of guild to list of channels where the bot will respond.
# If guild not found or channel list is empty then the bot will
# respond in all channels.
SUPPORT_CHANNELS = defaultdict(list)

MR_SYNC_ENDPOINT = "https://mossranking.com/api/getdiscordusers.php"
GAMES_RE = re.compile(r"^games\[([A-Za-z0-9 ]+)\]$")


async def globally_block_dms(ctx):
    return ctx.guild is not None


async def is_support_channel(ctx):
    if ctx.guild is None:
        return False

    channels = SUPPORT_CHANNELS.get(str(ctx.guild.id))
    return str(ctx.message.channel.id) in channels


async def not_support_channel(ctx):
    if ctx.guild is None:
        return False

    channels = SUPPORT_CHANNELS.get(str(ctx.guild.id))
    return str(ctx.message.channel.id) not in channels


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
        aliases=['colour'],
        help=(
            "Set the color of your name.\n"
            "`none` can be passed to clear your color.\n"
            "Calling the command with no arguments will show available colors."
        ),
        brief="Set the color of your name.",
        usage="color_name",
    )
    @commands.check(is_support_channel)
    async def color(self, ctx, *args):
        guild_color_roles = self.get_guild_colors(ctx)

        # Check that the user passed a color at all
        if not args:
            img_file = make_available_colors_image(guild_color_roles)
            await ctx.send(
                "Available colors:", file=discord.File(img_file, "colors.png")
            )
            return

        requested_color = " ".join(args).strip().lower()
        if requested_color.lower() == "none":
            await ctx.author.remove_roles(*self.get_author_colors(ctx).values())
            await ctx.message.add_reaction("👍")
            return

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
        help=(
            "Set the pronouns you prefer.\n"
            "`none` can be passed to clear your pronoun roles.\n"
            "Calling the command with no arguments will show available pronouns."
        ),
        brief="Set the pronouns you prefer.",
        usage="pronouns",
    )
    @commands.check(is_support_channel)
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
        if len(requested_pronouns) == 1 and requested_pronouns[0].lower() == "none":
            await ctx.author.remove_roles(*self.get_author_pronouns(ctx).values())
            await ctx.message.add_reaction("👍")
            return

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
        usage="[adjective] [adjective] [adjective]",
    )
    @commands.check(not_support_channel)
    async def ushabti(self, ctx, adj1=None, adj2=None, adj3=None):
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

        today = datetime.datetime.utcnow()
        seed = int(f"{today.year:04}{today.month:02}{today.day:02}")
        for type_, adj in adjectives.items():
            if adj is None:
                adjectives[type_] = random.Random(seed).choice(
                    TYPE_TO_ADJECTIVES[type_]
                )

        await ctx.send(USHABTI_URL.format(**adjectives))


def parse_config(config_path):
    with config_path.open("r") as config_file:
        data = json.load(config_file)

    for guild, channels in data.get("support-channels", {}).items():
        SUPPORT_CHANNELS[guild] = channels

    return data


class GhistBotkeeper(commands.Bot):
    pass


class HelpCommand(commands.DefaultHelpCommand):
    def add_indented_commands(self, commands, *, heading, max_size=None):
        if not commands:
            return

        max_size = max_size or self.get_max_size(commands)
        get_width = discord.utils._string_width
        for command in commands:
            name = command.name
            if name == "help":
                continue
            width = max_size - (get_width(name) - len(name))
            entry = "{0:<{width}} {1}".format(name, command.short_doc, width=width)
            self.paginator.add_line(self.shorten_text(entry))

    def get_ending_note(self):
        command_name = self.invoked_with
        return "Type {0}{1} command for more info on a command.\n".format(
            self.clean_prefix, command_name
        )


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

    intents = discord.Intents.default()
    intents.members = True

    ghist = GhistBotkeeper(
        command_prefix=args.prefix, help_command=HelpCommand(), intents=intents
    )

    # Cog Setup
    ghist.add_cog(Color(ghist))
    ghist.add_cog(Pronouns(ghist))
    ghist.add_cog(Ushabti(ghist))

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

    ghist.run(TOKEN)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    main()
