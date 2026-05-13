from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

PRONOUNS_PREFIX = "Pronouns: "


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

    @app_commands.command(
        name="pronouns",
        description="Set the pronouns you prefer. Omit to see available. Use `none` to clear.",
    )
    @app_commands.describe(
        pronoun1="A pronoun, or `none` to clear all.",
        pronoun2="An optional second pronoun.",
        pronoun3="An optional third pronoun.",
    )
    async def pronouns(
        self,
        interaction: discord.Interaction,
        pronoun1: Optional[str] = None,
        pronoun2: Optional[str] = None,
        pronoun3: Optional[str] = None,
    ):
        available_pronouns = self.get_pronouns_roles(interaction.guild.roles)
        member = interaction.user

        requested_pronouns = [
            p.strip().lower() for p in (pronoun1, pronoun2, pronoun3) if p
        ]

        if not requested_pronouns:
            await interaction.response.send_message(
                "Available pronouns: {}".format(
                    ", ".join(f"`{pronoun}`" for pronoun in available_pronouns)
                ),
                ephemeral=True,
            )
            return

        author_pronoun_roles = self.get_pronouns_roles(member.roles)

        if "none" in requested_pronouns:
            if len(requested_pronouns) > 1:
                await interaction.response.send_message(
                    "Use `none` on its own to clear your pronouns.",
                    ephemeral=True,
                )
                return
            if author_pronoun_roles:
                await member.remove_roles(*author_pronoun_roles.values())
            await interaction.response.send_message(
                "Cleared your pronouns. 👍", ephemeral=True
            )
            return

        target_pronouns = []
        unavailable_pronouns = []

        for pronoun in requested_pronouns:
            target = available_pronouns.get(pronoun)
            if target is None:
                unavailable_pronouns.append(pronoun)
            else:
                target_pronouns.append(target)

        if unavailable_pronouns:
            await interaction.response.send_message(
                "You've specified an unavailable pronoun. If you think this pronoun "
                "should be available please message a moderator to get it added. "
                "Available pronouns are: {}".format(
                    ", ".join(f"`{pronoun}`" for pronoun in available_pronouns)
                ),
                ephemeral=True,
            )
            return

        await member.add_roles(*target_pronouns)

        roles_to_remove = set(author_pronoun_roles.values())
        roles_to_remove.difference_update(target_pronouns)
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        await interaction.response.send_message(
            "Set your pronouns to {}. 👍".format(
                ", ".join(f"`{p}`" for p in requested_pronouns)
            ),
            ephemeral=True,
        )

    @pronouns.autocomplete("pronoun1")
    @pronouns.autocomplete("pronoun2")
    @pronouns.autocomplete("pronoun3")
    async def pronoun_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        current_lower = current.lower()
        names = ["none"] + sorted(
            self.get_pronouns_roles(interaction.guild.roles).keys()
        )
        matches = [n for n in names if current_lower in n]
        return [app_commands.Choice(name=n, value=n) for n in matches[:25]]
