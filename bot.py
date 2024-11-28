import discord
from discord.ext import commands
import yt_dlp as youtube_dl
from dotenv import load_dotenv
import os

# Ensure 'downloads/' directory exists
os.makedirs('downloads', exist_ok=True)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('DISCORD_TOKEN')

# Logging for debugging purposes
if not BOT_TOKEN:
    print("Error: Bot token not found in environment variables.")
    exit(1)  # Exit if token is missing
else:
    print("Bot token loaded successfully.")

# Intents and bot setup
intents = discord.Intents.default()
intents.message_content = True  # Needed for reading messages
bot = commands.Bot(command_prefix="!", intents=intents)

# Global YouTube Downloader options
# Global YouTube Downloader options with forced audio extraction
ydl_opts = {
    'format': 'bestaudio/best',  # Get the best audio quality
    'noplaylist': True,          # Don't download entire playlists
    'quiet': True,               # Suppress console output from yt-dlp
    'outtmpl': 'downloads/%(id)s.%(ext)s',  # Save the file to 'downloads' directory
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',  # Extract audio using FFmpeg
        'preferredcodec': 'mp3',      # Convert audio to MP3 format
        'preferredquality': '192',    # 192 kbps MP3
    }],
    'nocheckcertificate': True,    # Ignore certificate errors
    'extractaudio': True,          # Force audio extraction from video files
}


FFMPEG_OPTIONS = {
    'executable': 'ffmpeg',  # Assuming ffmpeg is in PATH
    'options': '-vn'         # Disable video
}

# Bot events
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Registered commands:")
    for command in bot.commands:
        print(f"- {command.name}")
    print(f"Current working directory: {os.getcwd()}")  # Debugging: Verify working directory

# Error handler for commands
@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"An error occurred: {str(error)}")
    print(f"Command error: {error}")

# Commands
@bot.command()
async def join(ctx):
    """Command for the bot to join the user's voice channel."""
    if ctx.author.voice:
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined {channel.name}")
    else:
        await ctx.send("You need to be in a voice channel for me to join!")

@bot.command()
async def leave(ctx):
    """Command for the bot to leave the voice channel."""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel.")
    else:
        await ctx.send("I'm not connected to a voice channel!")

@bot.command()
async def play(ctx, *, query: str):
    """Play audio from a given URL or keyword."""
    if not ctx.author.voice:
        await ctx.send("You need to join a voice channel first.")
        return

    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        voice_channel = await channel.connect()
    else:
        voice_channel = ctx.voice_client

    # Handle search terms or URLs
    if not query.startswith("http://") and not query.startswith("https://"):
        query = f"ytsearch:{query}"  # Use yt-dlp's search feature

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(query, download=True)  # Download the file

            if 'entries' in info_dict:
                info_dict = info_dict['entries'][0]  # Use the first entry if it's a search result

            song_url = info_dict.get('webpage_url', 'Unknown URL')
            song_title = info_dict.get('title', 'Unknown Title')
            song_path = f"downloads/{info_dict['id']}.mp3"  # Set path explicitly

            print(f"Downloaded file saved at: {song_path}, URL: {song_url}")  # Debugging: Confirm file path

            # Ensure the file exists before playing
            if not os.path.exists(song_path):
                await ctx.send("Error: The file could not be downloaded.")
                return

            # Play the audio and clean up after
            def after_playing(error):
                if error:
                    print(f"Playback error: {error}")
                if os.path.exists(song_path):
                    os.remove(song_path)
                    print(f"File deleted: {song_path}")  # Debugging: Confirm deletion

            voice_channel.play(discord.FFmpegPCMAudio(song_path, **FFMPEG_OPTIONS), after=after_playing)
            await ctx.send(f"Now playing: [{song_title}]({song_url})")

    except youtube_dl.utils.DownloadError as e:
        await ctx.send("Error downloading the song.")
        print(f"Download error: {e}")
    except Exception as e:
        await ctx.send("An unexpected error occurred.")
        print(f"Unexpected error: {e}")

@bot.command()
async def stop(ctx):
    """Stops the currently playing music."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Music stopped.")
    else:
        await ctx.send("No music is currently playing!")

@bot.command()
async def pause(ctx):
    """Pauses the currently playing music."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Music paused.")
    else:
        await ctx.send("No music is currently playing!")

@bot.command()
async def resume(ctx):
    """Resumes paused music."""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Music resumed.")
    else:
        await ctx.send("No music is currently paused!")

@bot.command()
async def commands_list(ctx):
    """Sends a list of registered commands."""
    commands = [cmd.name for cmd in bot.commands]
    await ctx.send(f"Registered commands: {', '.join(commands)}")

@bot.command(name='debug_commands')
async def debug_commands(ctx):
    """Lists all registered commands for debugging."""
    commands_list = [command.name for command in bot.commands]
    await ctx.send(f"Registered commands: {', '.join(commands_list)}")

# Run the bot
if __name__ == "__main__":
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("Failed to start bot: No token provided.")
