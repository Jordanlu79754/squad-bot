"""Runner for the Helldivers 2 and patch notes cogs.

Kept separate from bot.py on purpose: the music code depends on yt-dlp
extraction that YouTube currently breaks, and there is no reason these
features should be unavailable because of that. The cogs are ordinary
discord.py extensions, so once bot.py is working again they drop straight in:

    await bot.load_extension("cogs.helldivers_cog")
    await bot.load_extension("cogs.patchnotes_cog")

bot.py also needs a `bot.state = State()` before loading them.

Environment (.env):
    DISCORD_TOKEN     required
    HD2_CHANNEL_ID    channel for automatic announcements (optional)
    PATCH_CHANNEL_ID  overrides HD2_CHANNEL_ID for patch notes (optional)
    HD2_CONTACT       contact string sent to the community API (please set)
"""

from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from features.state import State

EXTENSIONS = ("cogs.helldivers_cog", "cogs.patchnotes_cog")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hd2bot")


def build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
    bot.state = State("bot_state.json")

    @bot.event
    async def on_ready():
        log.info("connected as %s in %d server(s)", bot.user, len(bot.guilds))

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        log.warning("%s -> %s", ctx.command, error)
        await ctx.send(f"That did not work: {error}")

    @bot.command(aliases=["h"])
    async def helpme(ctx):
        await ctx.send(
            "**Helldivers 2**\n"
            "`!mo` current Major Order and whether we are on pace\n"
            "`!planets [n]` busiest planets and their liberation rate\n\n"
            "**Patch notes**\n"
            "`!patch [lol|tft|val|all]` latest patch notes"
        )

    return bot


async def main() -> None:
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set. Put it in .env (which must stay untracked).")

    if os.getenv("HD2_CONTACT") is None:
        log.warning(
            "HD2_CONTACT is unset. The Helldivers community API asks callers to "
            "identify themselves; set it to an email or GitHub URL."
        )

    bot = build_bot()
    async with bot:
        for extension in EXTENSIONS:
            await bot.load_extension(extension)
            log.info("loaded %s", extension)
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
