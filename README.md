# squad-bot

A Discord bot for my friend group: patch-note alerts for League of Legends,
TFT and VALORANT, live Helldivers 2 war tracking, a voice music player and
four minigames.

It started as my CS50 final project ([video demo](https://youtu.be/XwSOVHE9NWI))
and has grown since.

```
!patch tft        latest Teamfight Tactics patch notes
!patch all        latest notes for League, TFT and VALORANT
!mo               Helldivers 2 Major Order, and whether it's on pace to finish
!war              active Helldivers 2 planets
!play <song>      queue a song in your voice channel
!ct               country flag trivia (250 countries)
!ttt @friend      two-player tic-tac-toe
!cl               list every command
```

## Features

### Riot patch notes (`!patch`)
Posts new League of Legends, TFT and VALORANT patch notes to a channel as
soon as they're published. You can also look up the latest ones on demand.

Riot has no public patch-notes API, so the bot reads the public news listing
pages. **Article URLs are used as stable identifiers.** A patch note gets
one URL and keeps it, so "have I seen this URL before?" is a reliable test
for "is this patch new?" The bot doesn't parse dates or article bodies. A bot
that breaks every time Riot reshuffles a page template is worse than one that
just links out.

On the first poll for each game, the bot records the existing articles
quietly instead of flooding the channel with old patches.

### Helldivers 2 war tracking (`!mo`, `!war`)
The game shows the Major Order's current progress, but not whether that
progress is moving fast enough. `!mo` samples progress over time and
estimates whether the community will finish before the order expires.

### Music player (`!play`, `!queue`, `!skip`, ...)
A voice-channel music player with an asynchronous queue. Songs advance on a
playback callback rather than a blocking wait, so the bot stays responsive
while `skip`, `remove` and `prioritize` change the queue it's playing from.

### Minigames
Country flag trivia (250 countries), two-player tic-tac-toe, truth or dare
and a magic 8-ball. Inputs are validated and prompts time out, because people
will spam bot commands.

## Running it

Requires Python 3.13+ and [FFmpeg](https://ffmpeg.org/) on your `PATH`.

```bash
pip install -r requirements.txt
```

Create a `.env` file (git-ignored, so it's never committed):

```
DISCORD_TOKEN=your-bot-token
HD2_CHANNEL_ID=channel-id-for-announcements     # optional
PATCH_CHANNEL_ID=channel-id-for-patch-notes     # optional, overrides the above
HD2_CONTACT=your-contact-for-the-community-api  # please set
```

```bash
python bot.py      # music + minigames
python hd2bot.py   # patch notes + Helldivers 2 tracking
```

## Tests

```bash
python -m pytest -q    # 55 tests
```

The tests cover the patch-note and Helldivers 2 modules and never touch the
network. Each feature is split into a pure "decide what this data means"
layer (`features/`) and a thin Discord layer (`cogs/`), so the logic can be
tested without a live bot.

## Design notes and bugs worth remembering

- **`campaign.faction` in the Helldivers 2 API is always "Humans".** It names
  who runs the campaign, not who is being fought. The enemy has to come from
  the planet's current owner.
- **discord.py below 2.5 can't run on Python 3.13.** It imports the standard
  library `audioop` module, which 3.13 removed, so the original pin couldn't
  even start.
- **The patch-notes and Helldivers features run separately from `bot.py`**
  (`hd2bot.py`), so a breakage in the music code can't take them down. The
  cogs are ordinary discord.py extensions and can be loaded into `bot.py`
  later.

## Known limitations

- **Music playback is currently broken.** YouTube changed how playback works,
  which breaks yt-dlp extraction. That's a dependency on a third-party
  service, and fixing it is next.
- `bot.py` is still a single file from the original CS50 version and has no
  tests. The newer features show the structure it should move to.
