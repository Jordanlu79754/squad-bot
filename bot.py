import discord
from discord.ext import commands
import yt_dlp as youtube_dl
from dotenv import load_dotenv
import os
import time  # Added to handle timing for file deletion
import asyncio
import random

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

INITIAL_VOLUME = 0.8  # 80% volume

# Global YouTube Downloader options
ydl_opts = {
    'format': 'bestaudio/best',  # Get the best audio quality
    'noplaylist': False,         # Don't download entire playlists initially
    'quiet': True,               # Suppress console output from yt-dlp
    'no_warnings': True,         # Suppress warnings
    'outtmpl': 'downloads/%(id)s.%(ext)s',  # Save the file to 'downloads' directory
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',  # Extract audio using FFmpeg
        'preferredcodec': 'mp3',      # Convert audio to MP3 format
        'preferredquality': '192',    # 192 kbps MP3
    }],
    'nocheckcertificate': True,    # Ignore certificate errors
    'extractaudio': True,          # Force audio extraction from video files
    'cookiefile': 'www.youtube.com_cookies.txt',  # Path to the YouTube cookies file
}

FFMPEG_OPTIONS = {
    'executable': 'ffmpeg',  # Assuming ffmpeg is in PATH
    'options': '-vn'         # Disable video
}

# Song queue initialization
song_queue = []  # Stores a list of queued songs

# Loads text file for truth or dare
def load_prompts(filename):
    with open(filename, 'r') as file:
        prompts = file.readlines()
    return [prompt.strip() for prompt in prompts]

# Truth or dare 
truths = load_prompts('truth.txt')
dares = load_prompts('dare.txt')
truths18 = load_prompts('truth18.txt')
dares18 = load_prompts('dare18.txt')

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

            # Add the song to the queue
            song_queue.append({
                'path': song_path,
                'title': song_title,
                'url': song_url
            })

            # Start playing if nothing is currently playing
            if not ctx.voice_client.is_playing():
                await play_next(ctx)

    except youtube_dl.utils.DownloadError as e:
        await ctx.send("Error downloading the song.")
        print(f"Download error: {e}")
    except Exception as e:
        await ctx.send("An unexpected error occurred.")
        print(f"Unexpected error: {e}")

@bot.command()
async def play_playlist(ctx, *, playlist_url: str):
    """Play all songs from a playlist URL."""
    # Check if the user is in a voice channel
    if not ctx.author.voice:
        await ctx.send("You need to join a voice channel first.")
        return

    # Get the voice channel of the user
    voice_channel = ctx.author.voice.channel

    # Join the voice channel if the bot is not already in one
    if not ctx.voice_client:
        await voice_channel.connect()

    # Extract playlist information
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(playlist_url, download=True)  # Download the playlist

            if 'entries' in info_dict:
                for entry in info_dict['entries']:
                    song_url = entry.get('webpage_url', 'Unknown URL')
                    song_title = entry.get('title', 'Unknown Title')
                    song_path = f"downloads/{entry['id']}.mp3"  # Set path explicitly

                    print(f"Downloaded file saved at: {song_path}, URL: {song_url}")  # Debugging: Confirm file path

                    # Ensure the file exists before adding to queue
                    if not os.path.exists(song_path):
                        await ctx.send(f"Error: The file for {song_title} could not be downloaded.")
                        continue

                    # Add the song to the queue
                    song_queue.append({
                        'path': song_path,
                        'title': song_title,
                        'url': song_url
                    })

            # Start playing the first song if nothing is currently playing
            if not ctx.voice_client.is_playing():
                await play_next(ctx)

        except youtube_dl.utils.DownloadError as e:
            await ctx.send("Error downloading the playlist.")
            print(f"Download error: {e}")
        except Exception as e:
            await ctx.send("An unexpected error occurred.")
            print(f"Unexpected error: {e}")

async def play_next(ctx):
    """Play the next song in the queue."""
    if song_queue:
        song = song_queue.pop(0)  # Get the first song in the queue
        song_path = song['path']
        song_title = song['title']
        song_url = song['url']

        def after_playing(error):
            if error:
                print(f"Playback error: {error}")

            # Wait for ffmpeg process to terminate and the file to be released
            # Use the bot's event loop to schedule the coroutine in the main thread
            asyncio.run_coroutine_threadsafe(after_playing_async(ctx, song_path), ctx.bot.loop)

        # Check if voice_channel exists before playing
        voice_channel = ctx.voice_client
        if voice_channel:
            ffmpeg_options = {
                'executable': 'ffmpeg',
                'options': f'-vn -filter:a "volume={INITIAL_VOLUME}"'
            }
            voice_channel.play(discord.FFmpegPCMAudio(song_path, **ffmpeg_options), after=after_playing)
            await ctx.send(f"Now playing: [{song_title}]({song_url})")
        else:
            await ctx.send("Not connected to a voice channel.")
    else:
        await ctx.send("Queue is empty. Disconnecting...")
        await ctx.voice_client.disconnect()

# Define the async function that handles file deletion
async def after_playing_async(ctx, song_path):
    """Handle the cleanup and file deletion after the song finishes."""
    # Wait for ffmpeg process to terminate and the file to be released
    await asyncio.sleep(1)  # Non-blocking sleep

    try:
        os.remove(song_path)
        print(f"File deleted: {song_path}")
    except PermissionError as e:
        print(f"PermissionError: {e}. Could not delete file.")

    # After playback finishes, automatically start the next song if available
    if song_queue:
        await play_next(ctx)  # Pass ctx to `play_next` to continue the queue

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
async def prioritize(ctx, position: int):
    """Move a song to the top of the queue."""
    if position < 1 or position > len(song_queue):
        await ctx.send("Invalid position! Use a number corresponding to the song's position in the queue.")
        return
    
    song = song_queue.pop(position - 1)  # Remove the song from its position
    song_queue.insert(0, song)  # Add the song to the top of the queue
    await ctx.send(f"Prioritized: {song['title']} and moved it to the top of the queue.")

@bot.command()
async def skip(ctx):
    """Skips the currently playing song."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()  # Stops the current song
        await play_next(ctx)  # Play the next song in the queue (ensure play_next is awaited)
    else:
        await ctx.send("No music is currently playing!")

@bot.command()
async def commands_list(ctx):
    """Sends a list of registered commands."""
    commands = [cmd.name for cmd in bot.commands]
    await ctx.send(f"Registered commands: {', '.join(commands)}")

@bot.command()
async def remove(ctx, position: int):
    """Remove a song from the queue by its position."""
    if position < 1 or position > len(song_queue):
        await ctx.send("Invalid position! Use a number corresponding to the song's position in the queue.")
        return
    
    removed_song = song_queue.pop(position - 1)
    await ctx.send(f"Removed: {removed_song['title']} from the queue.")

@bot.command(name="queue")
async def show_queue(ctx):
    """Shows the current song queue."""
    if not song_queue:
        await ctx.send("The queue is currently empty!")
        return
    
    queue_list = "\n".join([f"{idx+1}. {song['title']}" for idx, song in enumerate(song_queue)])
    await ctx.send(f"**Current Queue:**\n{queue_list}")

# Bot command for !truth
@bot.command()
async def truth(ctx):
    truth_prompt = random.choice(truths)
    await ctx.send(truth_prompt)

# Bot command for !dare
@bot.command()
async def dare(ctx):
    dare_prompt = random.choice(dares)
    await ctx.send(dare_prompt)

# Bot command for !truth18
@bot.command()
async def truth18(ctx):
    truth_prompt = random.choice(truths18)
    await ctx.send(truth_prompt)

# Bot command for !dare18
@bot.command()
async def dare18(ctx):
    dare_prompt = random.choice(dares18)
    await ctx.send(dare_prompt)

# Run the bot
if __name__ == "__main__":
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("Failed to start bot: No token provided.")
