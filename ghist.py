import os
import argparse
import asyncio
import logging

from discord.ext import commands


TOKEN = os.environ["GHIST_BOT_TOKEN"]


@commands.command()
async def color(ctx, *, arg: str):
    await ctx.send(arg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prefix", default="!", help="The prefix this bot uses on bot commands."
    )
    args = parser.parse_args()

    ghist = commands.Bot(command_prefix=args.prefix)
    ghist.add_command(color)
    ghist.run(TOKEN)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    main()
