import discord
from discord.ext import commands

bot = commands.Bot(command_prefix="!")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Registered commands:")
    for command in bot.commands:
        print(f"- {command.name}")

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send("Pong!")

bot.run("YOUR_BOT_TOKEN")
