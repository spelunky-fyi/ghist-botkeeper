import argparse
import asyncio
import logging
import os

from discord.ext import commands

TOKEN = os.environ["GHIST_BOT_TOKEN"]
COLOR_PREFIX = "Color: "


def get_colors_roles(roles):
    colors = {}
    for role in roles:
        if role.name.startswith(COLOR_PREFIX):
            colors[role.name[len(COLOR_PREFIX) :].lower()] = role
    return colors


def get_guild_colors(ctx):
    return get_colors_roles(ctx.guild.roles)


def get_author_colors(ctx):
    return get_colors_roles(ctx.author.roles)


@commands.command(
    help="Set the color of your name.",
    brief="Set the color of your name.",
    usage="color_name",
)
async def color(ctx, *args):
    # Check that the user passed a color at all
    if not args:
        await ctx.send("See pins for available colors.")
        return

    requested_color = " ".join(args).strip().lower()
    guild_color_roles = get_guild_colors(ctx)

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
    roles_to_remove = set(get_author_colors(ctx).values())
    roles_to_remove.discard(target_role)
    if roles_to_remove:
        await ctx.author.remove_roles(*roles_to_remove)

    await ctx.message.add_reaction("👍")


async def globally_block_dms(ctx):
    return ctx.guild is not None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prefix", default="!", help="The prefix this bot uses on bot commands."
    )
    args = parser.parse_args()

    # Change only the no_category default string
    help_command = commands.DefaultHelpCommand(
        no_category = 'Commands'
    )

    ghist = commands.Bot(command_prefix=args.prefix, help_command=help_command)
    ghist.add_command(color)
    ghist.add_check(globally_block_dms)
    ghist.run(TOKEN)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    main()
