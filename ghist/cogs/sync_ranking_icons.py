import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import aiohttp
from discord.ext import commands, tasks
from discord.member import Member
from discord.role import Role
from discord.user import User

BADGE_PREFIX = "Badge: "
MR_SYNC_KEY = os.environ["MR_SYNC_KEY"]
MR_SYNC_ENDPOINT = "https://mossranking.com/api/getdiscorduserranking.php"


@dataclass
class Ranking:
    min_points: int
    max_points: int
    role: str


@dataclass
class Game:
    ranking_id: int
    role: str
    rankings: List[Ranking]


GAMES = [
    Game(
        ranking_id=17,
        role="Badge: MR-Sync Classic",
        rankings=[
            Ranking(min_points=0, max_points=109_999, role="Badge: Classic Mines"),
            Ranking(
                min_points=110_000, max_points=219_999, role="Badge: Classic Jungle"
            ),
            Ranking(
                min_points=220_000, max_points=329_999, role="Badge: Classic Ice Caves"
            ),
            Ranking(
                min_points=330_000, max_points=440_000, role="Badge: Classic Temple"
            ),
        ],
    ),
    Game(
        ranking_id=1,
        role="Badge: MR-Sync HD",
        rankings=[
            Ranking(min_points=0, max_points=353_999, role="Badge: HD Mines"),
            Ranking(min_points=354_000, max_points=707_999, role="Badge: HD Jungle"),
            Ranking(
                min_points=708_000, max_points=1_061_999, role="Badge: HD Ice Caves"
            ),
            Ranking(
                min_points=1_062_000, max_points=1_415_999, role="Badge: HD Temple"
            ),
            Ranking(min_points=1_416_000, max_points=1_770_001, role="Badge: HD Hell"),
        ],
    ),
    Game(
        ranking_id=20,
        role="Badge: MR-Sync 2",
        rankings=[
            Ranking(min_points=0, max_points=178_000, role="Badge: 2 Dwelling"),
            Ranking(min_points=178_001, max_points=356_000, role="Badge: 2 Volcana"),
            Ranking(
                min_points=356_001, max_points=534_000, role="Badge: 2 Olmec's Lair"
            ),
            Ranking(
                min_points=534_001, max_points=712_000, role="Badge: 2 Temple of Anubis"
            ),
            Ranking(
                min_points=712_001, max_points=890_000, role="Badge: 2 City of Gold"
            ),
            Ranking(min_points=890_001, max_points=1_068_000, role="Badge: 2 Duat"),
            Ranking(
                min_points=1_068_001, max_points=1_246_000, role="Badge: 2 Ice Caves"
            ),
            Ranking(
                min_points=1_246_001, max_points=1_424_000, role="Badge: 2 Neo Babylon"
            ),
            Ranking(
                min_points=1_424_001, max_points=1_602_000, role="Badge: 2 Sunken City"
            ),
            Ranking(
                min_points=1_602_001, max_points=1_780_000, role="Badge: 2 Cosmic Ocean"
            ),
        ],
    ),
]


class MossRankingIconSync(commands.Cog):
    def __init__(self, bot, guild_id):
        self.bot = bot
        self.guild_id = guild_id

        self.syncer.start()  # pylint: disable=no-member

    async def get_points_for_game(
        self, game: Game, discord_id=None
    ) -> Optional[Dict[int, int]]:

        params = {
            "key": MR_SYNC_KEY,
            "id_ranking": game.ranking_id,
        }
        if discord_id is not None:
            params["discord_id"] = discord_id

        async with aiohttp.ClientSession() as session:
            async with session.get(MR_SYNC_ENDPOINT, params=params) as req:
                if req.status != 200:
                    return
                data = await req.json()

        return {int(key): int(value) for key, value in data.items()}

    def get_badges_roles(self, guild):
        roles = {}
        for role in guild.roles:
            if role.name.startswith(BADGE_PREFIX):
                roles[role.name] = role
        return roles

    def get_ranking_roles(self, game: Game, roles: Dict[str, Role]):
        ranking_roles = set()
        for ranking in game.rankings:
            ranking_role = roles.get(ranking.role)
            if not ranking_role:
                continue
            ranking_roles.add(ranking_role)
        return ranking_roles

    @staticmethod
    def get_ranking_for_points(points, game: Game) -> Optional[Ranking]:
        for ranking in game.rankings:
            if points >= ranking.min_points and points <= ranking.max_points:
                return ranking

    async def sync_role_icons_for_game(
        self, members: List[Member], game: Game, roles: Dict[str, Role], discord_id=None
    ):

        game_sync_role = roles.get(game.role)
        if not game_sync_role:
            return

        ranking_roles = self.get_ranking_roles(game, roles)

        points_by_discord_id = await self.get_points_for_game(game, discord_id)
        # Safety check in case api returns empty data
        if not points_by_discord_id:
            return

        for member in members:
            points = points_by_discord_id.get(member.id)

            # Don't have a sync role for this game. Make sure to clean up any orphaned roles
            if game_sync_role not in member.roles or not points:
                orphaned_roles = ranking_roles.intersection(member.roles)
                if orphaned_roles:
                    logging.info(
                        "Removing roles %s from user %s", orphaned_roles, member.name
                    )
                    await member.remove_roles(*orphaned_roles)
                continue

            target_ranking = self.get_ranking_for_points(points, game)
            target_role = roles.get(target_ranking.role)
            if not target_role:
                logging.warning("Something went wrong with %s", target_ranking)
                continue

            if target_role not in member.roles:
                logging.info("Adding role %s to user %s", target_role, member.name)
                await member.add_roles(target_role)

            leftover_roles = ranking_roles.difference([target_role]).intersection(
                member.roles
            )
            if leftover_roles:
                logging.info(
                    "Removing roles %s from user %s", leftover_roles, member.name
                )
                await member.remove_roles(*leftover_roles)

    async def sync_role_icons(self, discord_id=None):
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return

        if discord_id:
            members = [guild.get_member(discord_id)]
        else:
            members = guild.members

        roles = self.get_badges_roles(guild=guild)
        for game in GAMES:
            logging.info("Syncing for game role: %s", game.role)
            await self.sync_role_icons_for_game(members, game, roles, discord_id)

    @tasks.loop(seconds=300.0)
    async def syncer(self):
        await self.sync_role_icons()

    @syncer.before_loop
    async def before_syncer(self):
        logging.info("Waiting for bot to be ready before starting sync task...")
        await self.bot.wait_until_ready()

    @staticmethod
    def get_badge_sync_roles(roles):
        badge_sync_roles = set()
        for role in roles:
            if role.name.startswith("Badge: MR-Sync "):
                badge_sync_roles.add(role)
        return badge_sync_roles

    @commands.Cog.listener()
    async def on_member_update(self, before: User, after: User):
        before_badge_sync_roles = self.get_badge_sync_roles(before.roles)
        after_badge_sync_roles = self.get_badge_sync_roles(after.roles)

        if before_badge_sync_roles == after_badge_sync_roles:
            return

        await self.sync_role_icons(after.id)
