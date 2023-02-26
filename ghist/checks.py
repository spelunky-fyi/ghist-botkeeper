from collections import defaultdict


# Mapping of guild to list of channels where the bot will respond.
# If guild not found or channel list is empty then the bot will
# respond in all channels.
SUPPORT_CHANNELS = defaultdict(list)

DOGS_CHANNELS = set()

DAILY_CHANNELS = set()


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
