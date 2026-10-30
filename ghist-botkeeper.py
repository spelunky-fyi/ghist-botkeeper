import argparse
import json
import logging
import os
from pathlib import Path


import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv("ghist-bot.env")

from ghist.checks import (
    SUPPORT_CHANNELS,
    DOGS_CHANNELS,
    DAILY_CHANNELS,
    API_HELP_CHANNELS,
    globally_block_dms,
)
from ghist.cogs.color import Color
from ghist.cogs.spelunkicon import Spelunkicon
from ghist.cogs.sync_ranking_icons import MossRankingIconSync
from ghist.cogs.mr_sync import MossrankingSync
from ghist.cogs.pronouns import Pronouns
from ghist.cogs.ushabti import Ushabti
from ghist.cogs.daily_channel_titles import DailyChannelTitles
from ghist.cogs.modding_api import ModdingAPI


TOKEN = os.environ["GHIST_BOT_TOKEN"]


def parse_config(config_path):
    with config_path.open("r") as config_file:
        data = json.load(config_file)

    for guild, channels in data.get("support-channels", {}).items():
        SUPPORT_CHANNELS[guild] = channels

    DOGS_CHANNELS.update(set(data.get("dogs-channels", [])))
    DAILY_CHANNELS.update(set(data.get("daily-channels", [])))
    API_HELP_CHANNELS.update(set(data.get("api-channels", [])))

    return data


class GhistCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await globally_block_dms(interaction)

    async def on_error(self, interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            msg = "You can't use this command here."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return
        await super().on_error(interaction, error)


class GhistBotkeeper(commands.Bot):
    def __init__(self, *, config, **kwargs):
        super().__init__(**kwargs)
        self.config = config

    async def setup_hook(self):
        await self.add_cog(Color(self))
        await self.add_cog(Pronouns(self))
        await self.add_cog(Ushabti(self))
        await self.add_cog(Spelunkicon(self))
        await self.add_cog(DailyChannelTitles(self))
        await self.add_cog(ModdingAPI(self))

        if self.config.get("mr-sync"):
            await self.add_cog(
                MossrankingSync(
                    bot=self,
                    guild_id=self.config["mr-sync"]["guild-id"],
                    role_id=self.config["mr-sync"]["role-id"],
                    game_role_ids=self.config["mr-sync"].get("games", {}),
                )
            )
            await self.add_cog(
                MossRankingIconSync(
                    bot=self,
                    guild_id=self.config["mr-sync"]["guild-id"],
                )
            )

        guild_ids = self.config.get("guild-ids") or []
        if guild_ids:
            for guild_id in guild_ids:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logging.info(
                    "Synced %d slash commands to guild %s",
                    len(synced),
                    guild_id,
                )
        else:
            synced = await self.tree.sync()
            logging.info(
                "No guild-ids in config; synced %d slash commands globally",
                len(synced),
            )


def main():
    parser = argparse.ArgumentParser()
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
    intents.message_content = True

    ghist = GhistBotkeeper(
        config=config,
        command_prefix=commands.when_mentioned_or("?"),
        help_command=None,
        intents=intents,
        tree_cls=GhistCommandTree,
    )

    ghist.run(TOKEN)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    main()
