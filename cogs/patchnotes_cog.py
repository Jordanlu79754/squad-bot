"""Patch note commands and the background watcher for LoL, TFT and Valorant."""

from __future__ import annotations

import logging
import os

import aiohttp
import discord
from discord.ext import commands, tasks

from features import patchnotes as pn
from features.state import State

log = logging.getLogger(__name__)

POLL_MINUTES = 30

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; helldivers-discord-bot/0.1)",
    "Accept": "text/html",
}

COLOURS = {
    "lol": discord.Colour.from_rgb(200, 155, 60),
    "tft": discord.Colour.from_rgb(120, 110, 200),
    "valorant": discord.Colour.from_rgb(255, 70, 85),
}


class PatchNotes(commands.Cog):
    def __init__(self, bot: commands.Bot, state: State):
        self.bot = bot
        self.state = state
        self.session: aiohttp.ClientSession | None = None
        self.channel_id = int(os.getenv("PATCH_CHANNEL_ID", os.getenv("HD2_CHANNEL_ID", "0")))

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession(headers=BROWSER_HEADERS)
        self.watch_patches.start()

    async def cog_unload(self) -> None:
        self.watch_patches.cancel()
        if self.session:
            await self.session.close()

    async def _fetch(self, game: str) -> list[pn.PatchNote]:
        assert self.session is not None
        _, url, _ = pn.GAMES[game]
        async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as response:
            response.raise_for_status()
            return pn.parse_listing(game, await response.text())

    # ---------------------------------------------------------------- commands

    @commands.command(aliases=["patch", "notes"])
    async def patchnotes(self, ctx: commands.Context, game: str = "all"):
        """Latest patch notes. Usage: !patch [lol|tft|val|all]"""
        if game.lower() in ("all", "*"):
            wanted = list(pn.GAMES)
        else:
            resolved = pn.resolve_game(game)
            if resolved is None:
                await ctx.send("Pick one of: `lol`, `tft`, `val`, or `all`.")
                return
            wanted = [resolved]

        for key in wanted:
            try:
                notes = await self._fetch(key)
            except Exception as error:
                log.exception("patch fetch failed for %s", key)
                await ctx.send(f"Could not load {pn.GAMES[key][0]} patch notes: {error}")
                continue

            if not notes:
                await ctx.send(f"Found no patch notes for {pn.GAMES[key][0]}.")
                continue

            latest = notes[0]
            embed = discord.Embed(
                title=latest.title,
                url=latest.url,
                colour=COLOURS.get(key, discord.Colour.light_grey()),
            )
            if len(notes) > 1:
                previous = "\n".join(f"[{note.title}]({note.url})" for note in notes[1:4])
                embed.add_field(name="Previously", value=previous, inline=False)
            await ctx.send(embed=embed)

    # -------------------------------------------------------------- background

    @tasks.loop(minutes=POLL_MINUTES)
    async def watch_patches(self):
        """Announce patch notes we have not seen before."""
        for key in pn.GAMES:
            try:
                notes = await self._fetch(key)
            except Exception:
                log.exception("patch poll failed for %s", key)
                continue

            # The first poll for a game records everything silently; otherwise
            # a fresh install would dump the entire back catalogue at once.
            first_run = not self.state.has_seen_any(key)
            fresh = [note for note in notes if not self.state.is_patch_seen(key, note.url)]

            for note in fresh:
                self.state.mark_patch_seen(key, note.url)

            if fresh and not first_run and self.channel_id:
                channel = self.bot.get_channel(self.channel_id)
                if channel is not None:
                    for note in reversed(fresh):
                        await channel.send(
                            embed=discord.Embed(
                                title=f"New: {note.title}",
                                url=note.url,
                                colour=COLOURS.get(key, discord.Colour.light_grey()),
                            )
                        )

        self.state.save()

    @watch_patches.before_loop
    async def before_watch(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(PatchNotes(bot, bot.state))
