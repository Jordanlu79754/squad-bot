Summarization:
This final project is a Discord bot for a very popular application known as Discord. It includes features such as playing music and various minigames (Tic Tac Toe, Truth or Dare, Magic 8 Ball, and Country Trivia) to be played with other Discord users. This bot requries the installation of an application known as FFmpeg in order to play music (if you are running the bot, ignore if you are simply using the bot). Each Discord Bot requires an API token acquired from the Discord Developer Portal and is stored in the .env file (it is ignored by github for privacy reasons, update the API token in .env if needed instead of hardcoding it in bot.py).

Using:
The Discord bot can be connected to any server that the user has permission to invite and manage members (the discord bot will need permission to send messages and "speak" in voice calls). The incorporation of my Discord bot into any Discord servers (community of Discord users created by individuals) can be accessed through https://discord.com/oauth2/authorize?client_id=1309347693033820191. Use the prefix ! for any commands that the bot is programmed to do and use !cl or !commands_list to access all available commands.

Running:
1. Ensure that FFmpeg is installed on the device with the location of the installation accessbile by bot.py
2. Ensure that the following files exist:
- .env
- 48x48
- dare.txt
- dare18.txt
- magic8ball.txt
- truth.txt
- truth18.txt
- world.csv
- www.youtube.com_cookies.txt
3. Use 'python bot.py' to start the application and if it is connected to the Discord server, it will run

Files:
- .env: Used to store the Discord bot's API token (essentially the password to a Discord bot)
- 48x48: A folder storing CountryTwoLetterCode.png necessary for the Country Trivia game
- dare.txt: A text file required for prompts used for dares in Truth or Dare
- dare18.txt: A text file required for prompts used for dares18 in Truth or Dare
- magic8ball.txt: A text file required for prompts used for Magic 8 Ball
- truth.txt: A text file required for prompts used for truths in Truth or Dare
- truth18.txt: A text file required for prompts used for truths18 in Truth or Dare
- world.csv: A csv file used to store information about countries that is necessary for the Country Trivia game
- www.youtube.come_cookies.txt: A text file storing youtube login information necessary for age restrictions and bot prevention

Modifications:
- Replace the API token in .env to use the code for a separate Discord bot
- Replace the www.youtube.come_cookies.txt for personal YouTube account/information
- Mofidy the prompts in dare.txt, dare18.txt, magic8ball.txt, truth.txt, truth18.txt
- Modify audio processing settings in bot.py under ydl_opts

Youtube video presentation: 