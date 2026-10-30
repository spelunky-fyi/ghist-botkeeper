from collections import defaultdict

import discord


# Mapping of guild to list of channels where the bot will respond.
# If guild not found or channel list is empty then the bot will
# respond in all channels.
SUPPORT_CHANNELS = defaultdict(list)

DOGS_CHANNELS = set()

DAILY_CHANNELS = set()

API_HELP_CHANNELS = set()


async def globally_block_dms(interaction: discord.Interaction) -> bool:
    return interaction.guild is not None


async def is_support_channel(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False

    channels = SUPPORT_CHANNELS.get(str(interaction.guild.id)) or []
    return str(interaction.channel_id) in channels


async def not_support_channel(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False

    channels = SUPPORT_CHANNELS.get(str(interaction.guild.id)) or []
    return str(interaction.channel_id) not in channels


async def is_api_channel(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False

    # No channels configured means the command works everywhere
    if not API_HELP_CHANNELS:
        return True

    return str(interaction.channel_id) in API_HELP_CHANNELS
