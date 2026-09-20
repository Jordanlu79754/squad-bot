import discord
from discord.ext import commands
import yt_dlp as youtube_dl
from dotenv import load_dotenv
import os
import asyncio
import time
import random
import csv

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
    'noplaylist': False,         # Download entire playlists initially
    'quiet': True,               # Suppress console output from yt-dlp
    'no_warnings': True,         # Suppress warnings
    'outtmpl': 'downloads/%(id)s.%(ext)s',  # Save the file to 'downloads' directory
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',  # Extract audio using FFmpeg
        'preferredcodec': 'mp3',      # Convert audio to MP3 format
        'preferredquality': '192',    # 192 kbps MP3
    }],
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    },
    'nocheckcertificate': True,       # Ignore certificate errors
    'extractaudio': True,             # Force audio extraction from video files
    'cookiefile': 'www.youtube.com_cookies.txt',  # Path to the YouTube cookies file
}


FFMPEG_OPTIONS = {
    'executable': 'ffmpeg',  # Assuming ffmpeg is in PATH
    'options': '-vn'         # Disable video
}

# Song queue initialization
song_queue = []  # Stores a list of queued songs

# Loads text file for truth or dare prompts
def load_prompts(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        prompts = file.readlines()
    return [prompt.strip() for prompt in prompts]

# Truth or dare prompts
truths = load_prompts('truth.txt')
dares = load_prompts('dare.txt')
truths18 = load_prompts('truth18.txt')
dares18 = load_prompts('dare18.txt')

# Magic 8 ball prompts
magic8balltext = load_prompts('magic8ball.txt')

# CSV file reading for the Country Trivia game
def load_country_data(file_path):
    countries = []
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header
        for row in reader:
            country = {
                'alpha2': row[1],
                'name': row[3]  # This depends on the flag data format
            }
            countries.append(country)
    return countries

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

# Making the bot join the voice channel
@bot.command()
async def join(ctx):
    if ctx.author.voice:
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined {channel.name}")
    else:
        await ctx.send("You need to be in a voice channel for me to join!")

# Making the bot leave the voice channel
@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel.")
    else:
        await ctx.send("I'm not connected to a voice channel!")

# Command for playing song
@bot.command()
async def play(ctx, *, query: str):
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
        query = f"ytsearch:{query}"  # Use yt-dlp's search feature based on user input of the name of the song

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

# Command to play all the songs in a Youtube playlist 
@bot.command()
async def play_playlist(ctx, *, playlist_url: str):
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

#Play the next song in the queue
async def play_next(ctx):
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
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

# Define the async function that handles file deletion
async def after_playing_async(ctx, song_path):
    # Handle the cleanup and file deletion after the song finishes
    # Wait for ffmpeg process to terminate and the file to be released
    await asyncio.sleep(1)  # Non-blocking sleep

    try:
        os.remove(song_path) # Works most of the time for some reason
        print(f"File deleted: {song_path}")
    except PermissionError as e:
        print(f"PermissionError: {e}. Could not delete file.")

    # After playback finishes, automatically start the next song if available
    if song_queue:
        await play_next(ctx)  # Pass ctx to `play_next` to continue the queue

# Stops the currently playing music
@bot.command()
async def stop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Music stopped.")
    else:
        await ctx.send("No music is currently playing!")

# Pauses the currently playing music
@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Music paused.")
    else:
        await ctx.send("No music is currently playing!")

# Resume the paused music
@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Music resumed.")
    else:
        await ctx.send("No music is currently paused!")

# Move a song to the top of the queue
@bot.command()
async def prioritize(ctx, position: int):
    if position < 1 or position > len(song_queue):
        await ctx.send("Invalid position! Use a number corresponding to the song's position in the queue.")
        return
    
    song = song_queue.pop(position - 1)  # Remove the song from its position
    song_queue.insert(0, song)  # Add the song to the top of the queue
    await ctx.send(f"Prioritized: {song['title']} and moved it to the top of the queue.")

# Skips the currently playing song
@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()  # Stops the current song
        await play_next(ctx)  # Play the next song in the queue (ensure play_next is awaited)
    else:
        await ctx.send("No music is currently playing!")

# Sends a list of registered commands
@bot.command(aliases=["cl"])
async def commands_list(ctx):
    commands = []
    for cmd in bot.commands:
        if cmd.aliases:
            alias_list = ', '.join(cmd.aliases)
            commands.append(f"{cmd.name} (Also use: {alias_list})")
        else:
            commands.append(f"{cmd.name}")  # No aliases, just the command name

    # Construct the response message with proper formatting
    commands_message = "\n- ".join(commands)
    await ctx.send(f"Registered commands (Prefix: {bot.command_prefix}):\n- {commands_message}")

# Remove the song from queue by the position number
@bot.command()
async def remove(ctx, position: int):
    if position < 1 or position > len(song_queue):
        await ctx.send("Invalid position! Use a number corresponding to the song's position in the queue.")
        return
    
    removed_song = song_queue.pop(position - 1)
    await ctx.send(f"Removed: {removed_song['title']} from the queue.")

# Shows the current song queue
@bot.command(name="queue")
async def show_queue(ctx):
    if not song_queue:
        await ctx.send("The queue is currently empty!")
        return
    
    queue_list = "\n".join([f"{idx+1}. {song['title']}" for idx, song in enumerate(song_queue)])
    await ctx.send(f"**Current Queue:**\n{queue_list}")

# Bot command for truth or dare
@bot.command(aliases=["tod"])
async def truthordare(ctx):
    await ctx.send("Truth or dare? (Or truth18/dare18). Type 'quit' to stop")
    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel
    
    try:
        msg = await bot.wait_for('message', check=check, timeout=30.0)
        # Access the user's response
        user_response = msg.content.lower()
        if user_response == 'truth':
            truth_prompt = random.choice(truths)
            await ctx.send(truth_prompt)
        elif user_response == 'dare':
            dare_prompt = random.choice(dares)
            await ctx.send(dare_prompt)
        elif user_response == 'truth18':
            truths18_prompt = random.choice(truths18)
            await ctx.send(truths18_prompt)
        elif user_response == 'dare18':
            dares18_prompt = random.choice(dares18)
            await ctx.send(dares18_prompt)
        elif user_response == 'quit':
            await ctx.send("Alright, quitting Truth or Dare. Thanks for playing!")
            return  # End the function here to stop further processing
        else:
            await ctx.send("Invalid response. Please choose 'truth', 'dare', 'truth18', or 'dare18'.")
        
    except asyncio.TimeoutError:
        await ctx.send("You took too long to respond!")

# Magic 8 ball
@bot.command(aliases=["m8b"])
async def magic8ball(ctx):
    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    try:
        # Pick a random Magic 8-Ball response
        magic8ball_prompt = random.choice(magic8balltext)
        await ctx.send(magic8ball_prompt)
    except Exception as e:
        await ctx.send(f"Something went wrong: {str(e)}")

@bot.command(aliases=["ct"])
async def countrytrivia(ctx, num_questions: int = 5):
    await ctx.send("Ready? Type 'quit' to stop")
    num_questions = max(1, min(num_questions, 20))
    right_answers = 0
    countries = load_country_data('world.csv')

    for i in range(num_questions):
        country = random.choice(countries)
        flag = f"48x48/{country['alpha2'].lower()}.png"
        await ctx.send("Guess the country of this flag!")
        await ctx.send(file=discord.File(flag))

        def check(message):
            return message.author == ctx.author and message.channel == ctx.channel
        
        try:
            msg = await bot.wait_for('message', check=check, timeout=30.0)
            user_guess = msg.content.lower()

            if user_guess == country['name'].lower():
                await ctx.send("Correct! 🎉")
                right_answers = right_answers + 1
            elif user_guess == 'quit':
                await ctx.send("Game ended early. Thanks for playing!")
                return
            else:
                await ctx.send(f"Wrong! The correct answer was {country['name']}.")

        except asyncio.TimeoutError:
            await ctx.send(f"Time's up! The correct answer was {country['name']}.")
        # Remove the used country in the current game to avoid repetition
        countries.remove(country)

    await ctx.send(f"You got {right_answers}/{num_questions} correct answers!")

    await ctx.send("Trivia game over! Thanks for playing!")




# Print the game board
def print_board(board):
    return f"""
    ```
    {board[0]} | {board[1]} | {board[2]}
    ---------
    {board[3]} | {board[4]} | {board[5]}
    ---------
    {board[6]} | {board[7]} | {board[8]}
    ```
    """

# Check if a player has won
def check_winner(board, player):
    win_conditions = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
        [0, 4, 8], [2, 4, 6]  # Diagonals
    ]
    for condition in win_conditions:
        if board[condition[0]] == board[condition[1]] == board[condition[2]] == player:
            return True
    return False

# Check if the game is a draw
def check_draw(board):
    return all(spot != " " for spot in board)

# Tic Tac Toe Game Command with alias
@bot.command(aliases=["ttt"])
async def tictactoe(ctx, opponent: discord.User):
    if opponent.bot:
        await ctx.send("You can't play Tic Tac Toe with a bot!")
        return

    # Initialize the board with empty spaces
    board = [" "] * 9
    current_player = ctx.author  # The first player is the one who invoked the command
    current_symbol = "X"  # X always starts
    players = {ctx.author: "X", opponent: "O"}

    await ctx.send(f"Starting a game of Tic Tac Toe! {ctx.author.mention} (X) vs {opponent.mention} (O). Use `quit` to exit.")

    # Display the empty board
    game_message = await ctx.send(print_board(board))

    # Define a check function for valid moves
    def check(msg):
        return (
            msg.author == current_player and
            (msg.content.isdigit() and int(msg.content) in range(1, 10) and board[int(msg.content) - 1] == " ") or
            msg.content.lower() == "quit"
        )

    while True:
        # Ask the current player for their move
        await ctx.send(f"{current_player.mention}, it's your turn! Type a number (1-9) to place your {current_symbol}.")

        try:
            # Wait for the player's input (the number they want to place their symbol on)
            move_msg = await bot.wait_for("message", check=check, timeout=60.0)

            if move_msg.content.lower() == "quit":
                await ctx.send(f"{current_player.mention} has ended the game. Thanks for playing!")
                return

            move = int(move_msg.content) - 1
        except asyncio.TimeoutError:
            await ctx.send(f"{current_player.mention} took too long! Game over.")
            return

        # Update the board
        board[move] = current_symbol
        await game_message.edit(content=print_board(board))

        # Check if the current player has won
        if check_winner(board, current_symbol):
            await ctx.send(f"{current_player.mention} wins! 🎉")
            return

        # Check for a draw
        if check_draw(board):
            await ctx.send("It's a draw! 🙁")
            return

        # Switch turns
        current_player = opponent if current_player == ctx.author else ctx.author
        current_symbol = players[current_player]

# Run the bot
if __name__ == "__main__":
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("Failed to start bot: No token provided.")
