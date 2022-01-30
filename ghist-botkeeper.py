import argparse
import json
import logging
import os
from pathlib import Path


import discord
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv("ghist-bot.env")

from ghist.checks import SUPPORT_CHANNELS, globally_block_dms
from ghist.cogs.color import Color
from ghist.cogs.spelunkicon import Spelunkicon
from ghist.cogs.sync_ranking_icons import MossRankingIconSync
from ghist.cogs.mr_sync import MossrankingSync
from ghist.cogs.pronouns import Pronouns
from ghist.cogs.ushabti import Ushabti


TOKEN = os.environ["GHIST_BOT_TOKEN"]


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
    ghist.add_cog(Spelunkicon(ghist))

    if config.get("mr-sync"):
        ghist.add_cog(
            MossrankingSync(
                bot=ghist,
                guild_id=config["mr-sync"]["guild-id"],
                role_id=config["mr-sync"]["role-id"],
                game_role_ids=config["mr-sync"].get("games", {}),
            )
        )
        ghist.add_cog(
            MossRankingIconSync(
                bot=ghist,
                guild_id=config["mr-sync"]["guild-id"],
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
