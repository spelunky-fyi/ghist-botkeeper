import logging
import os
import re
from dataclasses import dataclass

from typing import Dict

import aiohttp
from discord.ext import commands, tasks

MR_SYNC_KEY = os.environ["MR_SYNC_KEY"]
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
