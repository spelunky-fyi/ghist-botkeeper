import difflib
from html.parser import HTMLParser
import logging

from discord.ext import commands
import aiohttp

from ghist.checks import API_HELP_CHANNELS


# Custom parser to isolate the list, find links, and extract their data
class LinkListParser(HTMLParser):
    def __init__(self, target_id):
        super().__init__()
        self.target_id = target_id
        self.inside_target_list = False
        self.list_depth = 0
        self.current_href = None
        self.current_text = []
        self.result_dict = {}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Check if we entered the target list container
        if attrs_dict.get("id") == self.target_id:
            self.inside_target_list = True

        if self.inside_target_list:
            if tag in ("ul", "ol"):
                self.list_depth += 1
            # Capture the href attribute if we hit a link inside our list
            elif tag == "a":
                self.current_href = attrs_dict.get("href", "")
                self.current_text = []  # Reset text collector for this link

    def handle_endtag(self, tag):
        if self.inside_target_list:
            if tag == "a" and self.current_href is not None:
                # Combine collected text fragments and pair with the link
                link_text = "".join(self.current_text).strip()
                if link_text:
                    self.result_dict[link_text] = self.current_href

                # Reset link state
                self.current_href = None

            elif tag in ("ul", "ol"):
                self.list_depth -= 1
                # Exit parsing state once we leave the primary parent list
                if self.list_depth == 0:
                    self.inside_target_list = False

    def handle_data(self, data):
        # Accumulate text only if we are currently inside an <a> tag within the target list
        if self.inside_target_list and self.current_href is not None:
            self.current_text.append(data)


class ModdingAPI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(10))

    def is_in_allowed_channel():
        async def predicate(ctx: commands.Context):
            if ctx.guild is None:
                return False

            if not API_HELP_CHANNELS:
                return True

            if ctx.channel.id in API_HELP_CHANNELS:
                return True

            return False

        return commands.check(predicate)

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        if isinstance(error, commands.CheckFailure):
            # suppress console errors when the custom check fails
            return

        self.bot.dispatch("command_error", ctx, error)

    @commands.command()
    @is_in_allowed_channel()
    async def api(self, ctx: commands.Context, *, search_string: str = None):
        """Search Spelunky2 modding API"""
        api_lookup: dict[str, str] = None
        url = "https://spelunky-fyi.github.io/overlunky/"

        if not search_string:
            await ctx.reply(f"[Overlunky/Playlunky Lua API](<{url}>)")
            return

        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                if response.status == 200:
                    html_content = await response.text()
                    if not html_content:
                        logging.error("Received empty result from modding API page")
                        await ctx.reply(
                            "Received empty result from modding API page :("
                        )
                        return
                    parser = LinkListParser(target_id="toc")
                    parser.feed(html_content)
                    api_lookup = parser.result_dict
                else:
                    logging.info(
                        f"Modding API page returned status code: {response.status}"
                    )
                    await ctx.reply("Could not reach API page :(")
                    return
        except Exception:
            logging.exception("Could not reach modding API page:")
            await ctx.reply("Could not reach API page :(")
        else:
            if not api_lookup:
                logging.error("Did not get lookup list from modding API page")
                await ctx.reply("Could not reach API page :(")
                return

            api_results = []

            for name, tag in api_lookup.items():
                # exact
                if search_string.lower() == name.lower():
                    api_results.insert(0, f"[{name}](<{url}{tag}>)")

                # partial
                elif search_string.lower() in name.lower():
                    api_results.append(f"[{name}](<{url}{tag}>)")

                # add best matching ones (to account for spelling mistakes etc.)
                else:
                    # ndiff finds all additions (+) and subtractions (-)
                    diffs = difflib.ndiff(search_string.lower(), name.lower())
                    difference_count = sum(
                        1
                        for line in diffs
                        if line.startswith("+") or line.startswith("-")
                    )
                    if difference_count < 4:
                        api_results.append(f"[{name}](<{url}{tag}>)")

            if not api_results:
                await ctx.reply("No results :(")
            else:
                # give 5 maching results
                await ctx.reply("\n".join(api_results[:5]))
