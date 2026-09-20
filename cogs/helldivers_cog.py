"""Helldivers 2 commands and the background war watcher."""

from __future__ import annotations

import logging
import os

import aiohttp
import discord
from discord.ext import commands, tasks

from features import helldivers as hd
from features.state import State

log = logging.getLogger(__name__)

POLL_MINUTES = 15  # also the resolution of the progress-rate estimate


class Helldivers(commands.Cog):
    def __init__(self, bot: commands.Bot, state: State):
        self.bot = bot
        self.state = state
        self.session: aiohttp.ClientSession | None = None
        self.channel_id = int(os.getenv("HD2_CHANNEL_ID", "0"))
        self._announced_order: int | None = None

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession(headers=hd.HEADERS)
        self.watch_war.start()

    async def cog_unload(self) -> None:
        self.watch_war.cancel()
        if self.session:
            await self.session.close()

    async def _get(self, path: str):
        assert self.session is not None
        async with self.session.get(f"{hd.BASE_URL}{path}", timeout=aiohttp.ClientTimeout(total=20)) as response:
            response.raise_for_status()
            return await response.json()

    # ------------------------------------------------------------- formatting

    def _order_embed(self, order: hd.MajorOrder) -> discord.Embed:
        seconds_left = order.seconds_left()

        embed = discord.Embed(
            title=order.title.title(),
            description=order.briefing or "No briefing provided.",
            colour=discord.Colour.gold() if not order.complete else discord.Colour.green(),
        )

        for index, task in enumerate(order.tasks):
            rate = self.state.progress_rate(order.id, index)
            verdict = hd.project_task(task, rate, seconds_left)
            bar = hd.progress_bar(task.fraction)
            embed.add_field(
                name=hd.describe_task(task, index),
                value=f"`{bar}` {task.fraction * 100:.1f}%\n{verdict}",
                inline=False,
            )

        if seconds_left is not None:
            embed.set_footer(text=f"Time remaining: {hd.humanize_duration(seconds_left)}")
        return embed

    # ---------------------------------------------------------------- commands

    @commands.command(aliases=["mo", "order"])
    async def majororder(self, ctx: commands.Context):
        """Current Major Order, with whether we are on pace to finish it."""
        try:
            order = hd.parse_major_order(await self._get("/assignments"))
        except Exception as error:
            log.exception("major order fetch failed")
            await ctx.send(f"Could not reach the war API: {error}")
            return

        if order is None:
            await ctx.send("No Major Order is active right now.")
            return
        await ctx.send(embed=self._order_embed(order))

    @commands.command(aliases=["planets", "war"])
    async def frontline(self, ctx: commands.Context, count: int = 5):
        """Where the players are, and whether those planets are actually moving."""
        try:
            planets = hd.parse_planets(await self._get("/campaigns"))
        except Exception as error:
            log.exception("campaign fetch failed")
            await ctx.send(f"Could not reach the war API: {error}")
            return

        if not planets:
            await ctx.send("No active campaigns.")
            return

        embed = discord.Embed(
            title="Active front",
            description="Busiest planets right now.",
            colour=discord.Colour.blurple(),
        )
        for planet in planets[: max(1, min(count, 10))]:
            kind = "Defence" if planet.is_defense else "Liberation"
            # A planet gaining slower than the enemy regenerates is a planet
            # nobody is going to take, however good the percentage looks.
            regen = f" · enemy regen {planet.regen_per_hour:.1f}%/h" if planet.regen_per_hour else ""
            embed.add_field(
                name=f"{planet.name} ({planet.faction})",
                value=(
                    f"`{hd.progress_bar(planet.liberation / 100)}` "
                    f"{planet.liberation:.1f}% {kind.lower()}\n"
                    f"{planet.players:,} divers{regen}"
                ),
                inline=False,
            )
        await ctx.send(embed=embed)

    # -------------------------------------------------------------- background

    @tasks.loop(minutes=POLL_MINUTES)
    async def watch_war(self):
        """Sample progress, and speak up when the Major Order changes."""
        try:
            order = hd.parse_major_order(await self._get("/assignments"))
        except Exception:
            log.exception("war poll failed")
            return

        if order is None:
            return

        self.state.record_order_sample(order.id, [task.current for task in order.tasks])
        self.state.save()

        if self.channel_id and order.id != self._announced_order:
            # First run after a restart should not re-announce the order that
            # was already live before we started.
            if self._announced_order is not None:
                channel = self.bot.get_channel(self.channel_id)
                if channel is not None:
                    await channel.send("**New Major Order.**", embed=self._order_embed(order))
            self._announced_order = order.id

    @watch_war.before_loop
    async def before_watch(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Helldivers(bot, bot.state))
