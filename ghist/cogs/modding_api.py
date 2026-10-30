import asyncio
import difflib
import logging
import time
from html.parser import HTMLParser
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from ghist.checks import is_api_channel

API_URL = "https://spelunky-fyi.github.io/overlunky/"
CACHE_TTL = 60 * 60
MAX_RESULTS = 5
MAX_AUTOCOMPLETE = 25


# Collects {link text: href} for every link inside the element with target_id
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

        if attrs_dict.get("id") == self.target_id:
            self.inside_target_list = True

        if self.inside_target_list:
            if tag in ("ul", "ol"):
                self.list_depth += 1
            elif tag == "a":
                self.current_href = attrs_dict.get("href", "")
                self.current_text = []

    def handle_endtag(self, tag):
        if self.inside_target_list:
            if tag == "a" and self.current_href is not None:
                link_text = "".join(self.current_text).strip()
                if link_text:
                    self.result_dict[link_text] = self.current_href
                self.current_href = None

            elif tag in ("ul", "ol"):
                self.list_depth -= 1
                # Stop once we leave the outermost list
                if self.list_depth == 0:
                    self.inside_target_list = False

    def handle_data(self, data):
        if self.inside_target_list and self.current_href is not None:
            self.current_text.append(data)


def parse_toc(html_content):
    parser = LinkListParser(target_id="toc")
    parser.feed(html_content)
    return parser.result_dict


def search(lookup, query):
    query = query.strip().lower()
    lowered = {name.lower(): name for name in lookup}

    exact = []
    prefix = []
    partial = []
    for lower_name, name in lowered.items():
        if lower_name == query:
            exact.append(name)
        elif lower_name.startswith(query):
            prefix.append(name)
        elif query in lower_name:
            partial.append(name)

    results = exact + prefix + partial
    if len(results) < MAX_RESULTS:
        # Account for spelling mistakes
        close = difflib.get_close_matches(query, lowered, n=MAX_RESULTS, cutoff=0.75)
        results.extend(lowered[name] for name in close if lowered[name] not in results)

    return results


def format_link(name, href):
    return f"[{name}](<{API_URL}{href}>)"


class ModdingAPI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lookup = {}
        self.lookup_fetched_at = 0
        self.lookup_lock = asyncio.Lock()

    async def get_lookup(self):
        async with self.lookup_lock:
            if self.lookup and time.monotonic() - self.lookup_fetched_at < CACHE_TTL:
                return self.lookup

            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as session:
                    async with session.get(API_URL) as response:
                        response.raise_for_status()
                        html_content = await response.text()

                lookup = await asyncio.to_thread(parse_toc, html_content)
                if not lookup:
                    raise ValueError("No table of contents found on modding API page")
            except Exception:
                logging.exception("Failed to fetch modding API page.")
                # Fall back to stale results if we have them
                return self.lookup

            self.lookup = lookup
            self.lookup_fetched_at = time.monotonic()
            return self.lookup

    @app_commands.command(
        name="api",
        description="Search the Overlunky/Playlunky Lua API. Omit to get a link to the docs.",
    )
    @app_commands.describe(query="A function, type, or enum name to search for.")
    @app_commands.check(is_api_channel)
    async def api(self, interaction: discord.Interaction, query: Optional[str] = None):
        if not query:
            await interaction.response.send_message(
                f"[Overlunky/Playlunky Lua API](<{API_URL}>)"
            )
            return

        await interaction.response.defer(thinking=True)

        lookup = await self.get_lookup()
        if not lookup:
            await interaction.followup.send("Could not reach API page :(")
            return

        results = search(lookup, query)
        if not results:
            await interaction.followup.send("No results :(")
            return

        await interaction.followup.send(
            "\n".join(format_link(name, lookup[name]) for name in results[:MAX_RESULTS])
        )

    @api.autocomplete("query")
    async def api_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        # Only use what's already cached; autocomplete must respond quickly
        if not current or not self.lookup:
            return []

        return [
            app_commands.Choice(name=name[:100], value=name[:100])
            for name in search(self.lookup, current)[:MAX_AUTOCOMPLETE]
        ]

    @commands.Cog.listener()
    async def on_ready(self):
        # Warm the cache so autocomplete works right away
        await self.get_lookup()
