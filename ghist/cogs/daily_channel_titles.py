import logging
import re
import time
from datetime import datetime

from discord.ext import commands, tasks


from ghist.checks import DAILY_CHANNELS

TOPIC_RE = re.compile(r"^(.*)( \d\d\d\d-\d\d-\d\d started <t:\d+:R>.)(.*)$")


def get_updated_topic(original_topic, date_obj, date_str):
    re_match = TOPIC_RE.match(original_topic)
    unix_timestamp = int(time.mktime(date_obj.timetuple()))

    if not re_match:
        return "{} {} started <t:{}:R>.".format(
            original_topic, date_str, unix_timestamp
        )

    groups = re_match.groups()
    return "{} {} started <t:{}:R>.{}".format(
        groups[0], date_str, unix_timestamp, groups[2]
    )


class DailyChannelTitles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_known_date = None
        self.syncer.start()  # pylint: disable=no-member

    def get_today_str(self, dt_obj):
        return "{:04}-{:02}-{:02}".format(dt_obj.year, dt_obj.month, dt_obj.day)

    def should_sync(self, today_str):
        if self.last_known_date is None:
            return True

        return today_str != self.last_known_date

    @tasks.loop(seconds=60.0)
    async def syncer(self):
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        date_str = self.get_today_str(today)
        if not self.should_sync(date_str):
            return

        logging.info("Syncing for Date: %s", date_str)
        try:
            for channel_id in DAILY_CHANNELS:
                channel = self.bot.get_channel(int(channel_id))
                topic = get_updated_topic(channel.topic or "", today, date_str)
                await channel.edit(topic=topic)
                logging.info(
                    "Updating %s - %s to (%s)", channel.guild.name, channel.name, topic
                )

            self.last_known_date = date_str
        except Exception:
            logging.exception("Failed to sync daily channels.")

    @syncer.before_loop
    async def before_syncer(self):
        logging.info("Waiting for bot to be reading before starting sync task...")
        await self.bot.wait_until_ready()
