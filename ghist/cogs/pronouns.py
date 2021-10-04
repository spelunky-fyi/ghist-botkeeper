from discord.ext import commands

from ghist.checks import is_support_channel

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
