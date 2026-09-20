"""Patch note detection for League, TFT and Valorant.

Riot has no public patch-notes API, so this reads the public listing pages and
pulls the article links out of them. Those links are stable identifiers: a
patch note gets one URL and keeps it, so "have I seen this URL before?" is a
reliable test for "is this patch new?" without needing to parse dates.

Deliberately not parsing the article bodies. The pages are rendered by a CMS
whose internal structure can change without warning, and a bot that breaks
every time Riot reshuffles a template is worse than one that just links out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

GAMES = {
    "lol": (
        "League of Legends",
        "https://www.leagueoflegends.com/en-us/news/tags/patch-notes/",
        "https://www.leagueoflegends.com",
    ),
    "tft": (
        "Teamfight Tactics",
        "https://teamfighttactics.leagueoflegends.com/en-us/news/tags/patch-notes/",
        "https://teamfighttactics.leagueoflegends.com",
    ),
    "valorant": (
        "VALORANT",
        "https://playvalorant.com/en-us/news/tags/patch-notes/",
        "https://playvalorant.com",
    ),
}

ALIASES = {
    "league": "lol", "lol": "lol",
    "tft": "tft", "teamfight": "tft",
    "val": "valorant", "valorant": "valorant",
}

_LINK = re.compile(r'href="(/en-us/news/[^"?#]*patch[^"?#]*)"')
# Version numbers appear as ...-26-12-notes or ...-patch-17-2
_VERSION = re.compile(r"patch[a-z-]*?-(\d{1,2})-(\d{1,2})")


@dataclass(frozen=True)
class PatchNote:
    game: str          # short key, e.g. "lol"
    game_name: str     # display name
    version: str       # "26.12", or "" when it cannot be read from the slug
    url: str

    @property
    def title(self) -> str:
        if self.version:
            return f"{self.game_name} patch {self.version}"
        return f"{self.game_name} patch notes"

    def sort_key(self) -> tuple:
        if not self.version:
            return (0, 0)
        major, _, minor = self.version.partition(".")
        return (int(major), int(minor))


def parse_listing(game: str, html: str) -> list[PatchNote]:
    """Extract patch notes from a listing page, newest version first."""
    game_name, _, origin = GAMES[game]

    notes = {}
    for path in _LINK.findall(html):
        match = _VERSION.search(path)
        version = f"{int(match.group(1))}.{match.group(2)}" if match else ""
        url = origin + path
        notes[url] = PatchNote(game, game_name, version, url)

    return sorted(notes.values(), key=lambda note: note.sort_key(), reverse=True)


def resolve_game(name: str) -> str | None:
    return ALIASES.get(name.strip().lower())
