"""Helldivers 2 galactic war data.

Talks to the community API at helldivers2.dev. Everything that parses or
formats is a plain function over already-fetched payloads, so it can be tested
without touching the network.

The API asks callers to identify themselves with X-Super-Client and
X-Super-Contact headers. Set HD2_CONTACT so they can reach you if your bot
starts misbehaving -- it is a free service and being a good citizen is the
price of using it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

BASE_URL = "https://api.helldivers2.dev/api/v1"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "helldivers-discord-bot/0.1",
    "X-Super-Client": "helldivers-discord-bot",
    "X-Super-Contact": os.getenv("HD2_CONTACT", "unset"),
}

# Task types seen in Major Orders. Type 3 is the common "kill N of faction X".
TASK_KILL = 3
TASK_LIBERATE = 11
TASK_DEFEND = 13

FACTIONS = {1: "Humans", 2: "Terminids", 3: "Automatons", 4: "Illuminate"}


@dataclass(frozen=True)
class Task:
    kind: int
    current: int
    target: int
    faction: str | None

    @property
    def is_measurable(self) -> bool:
        """Whether a percentage means anything for this task.

        Kill tasks count up to a target. Liberation tasks are a flag: the
        planet is taken or it is not, and reporting "47% of one planet" from
        this endpoint would be inventing precision we do not have.
        """
        return self.kind == TASK_KILL and self.target > 0

    @property
    def fraction(self) -> float:
        if not self.is_measurable:
            return 1.0 if self.current else 0.0
        return min(1.0, self.current / self.target)

    @property
    def complete(self) -> bool:
        return self.fraction >= 1.0


@dataclass(frozen=True)
class MajorOrder:
    id: int
    title: str
    briefing: str
    tasks: list[Task]
    expires_at: datetime | None

    @property
    def complete(self) -> bool:
        return all(task.complete for task in self.tasks)

    def seconds_left(self, now: datetime | None = None) -> float | None:
        if self.expires_at is None:
            return None
        return (self.expires_at - (now or datetime.now(timezone.utc))).total_seconds()


@dataclass(frozen=True)
class Planet:
    name: str
    sector: str
    faction: str
    liberation: float       # percent liberated, 0-100
    players: int
    regen_per_hour: float   # percent the enemy claws back per hour
    is_defense: bool


def _parse_expiration(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_major_order(payload: list[dict]) -> MajorOrder | None:
    """Build a MajorOrder from the /assignments response, or None if idle."""
    if not payload:
        return None

    raw = payload[0]
    progress = raw.get("progress") or []
    tasks = []

    for index, task in enumerate(raw.get("tasks") or []):
        values = task.get("values") or []
        kind = task.get("type", -1)
        # For kill tasks the third value is the goal, and the first identifies
        # the faction being killed.
        target = values[2] if kind == TASK_KILL and len(values) > 2 else 0
        faction = FACTIONS.get(values[0]) if kind == TASK_KILL and values else None
        tasks.append(
            Task(
                kind=kind,
                current=progress[index] if index < len(progress) else 0,
                target=target,
                faction=faction,
            )
        )

    return MajorOrder(
        id=raw.get("id", 0),
        title=(raw.get("title") or "Major Order").strip(),
        briefing=(raw.get("briefing") or "").strip(),
        tasks=tasks,
        expires_at=_parse_expiration(raw.get("expiration")),
    )


def parse_planets(payload: list[dict]) -> list[Planet]:
    """Turn the /campaigns response into planets, busiest first."""
    planets = []

    for campaign in payload:
        planet = campaign.get("planet") or {}
        event = planet.get("event")
        statistics = planet.get("statistics") or {}

        if event:
            # A defence: health counts DOWN from max as the enemy pushes in,
            # so progress is how much of the assault has been held off.
            max_health = event.get("maxHealth") or 1
            health = event.get("health") or 0
            liberation = 100.0 * (1 - health / max_health)
        else:
            max_health = planet.get("maxHealth") or 1
            health = planet.get("health") or 0
            liberation = 100.0 * (1 - health / max_health)

        regen = planet.get("regenPerSecond") or 0.0
        # `campaign.faction` is always "Humans" -- it names who is running the
        # campaign, which is always us. The enemy is whoever holds the planet.
        enemy = planet.get("currentOwner") or campaign.get("faction") or "?"
        planets.append(
            Planet(
                name=(planet.get("name") or "Unknown").title(),
                sector=planet.get("sector") or "",
                faction=enemy,
                liberation=max(0.0, min(100.0, liberation)),
                players=statistics.get("playerCount") or 0,
                regen_per_hour=100.0 * regen * 3600 / max_health,
                is_defense=bool(event),
            )
        )

    planets.sort(key=lambda planet: planet.players, reverse=True)
    return planets


# ------------------------------------------------------------------ formatting


def humanize_count(value: int) -> str:
    for limit, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(value) >= limit:
            return f"{value / limit:.1f}{suffix}"
    return str(value)


def humanize_duration(seconds: float) -> str:
    if seconds <= 0:
        return "expired"
    hours, remainder = divmod(int(seconds), 3600)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {remainder // 60}m"
    return f"{remainder // 60}m"


def progress_bar(fraction: float, width: int = 12) -> str:
    filled = round(max(0.0, min(1.0, fraction)) * width)
    return "█" * filled + "░" * (width - filled)


def project_task(task: Task, rate_per_second: float | None, seconds_left: float | None) -> str:
    """One line of plain English about whether this task will finish in time.

    This is the whole point of the bot: the game shows you the current number,
    but not whether the number is moving fast enough.
    """
    if task.complete:
        return "done"
    if not task.is_measurable:
        return "in progress"
    if seconds_left is None or seconds_left <= 0:
        return "no deadline"

    remaining = task.target - task.current
    needed_rate = remaining / seconds_left

    if rate_per_second is None:
        return f"needs {humanize_count(int(needed_rate * 3600))}/h from here"
    if rate_per_second <= 0:
        return "going backwards"

    projected = task.current + rate_per_second * seconds_left
    share = projected / task.target
    finishes_in = remaining / rate_per_second

    if share >= 1.0:
        return f"on pace — done in ~{humanize_duration(finishes_in)}"
    return f"off pace — lands at ~{share * 100:.0f}% of target"


def describe_task(task: Task, index: int) -> str:
    if task.is_measurable:
        target = f"{humanize_count(task.current)} / {humanize_count(task.target)}"
        label = f"Kill {task.faction}" if task.faction else "Objective"
        return f"{label}: {target}"
    verb = {TASK_LIBERATE: "Liberate", TASK_DEFEND: "Defend"}.get(task.kind, "Objective")
    return f"{verb} objective {index + 1}: {'complete' if task.complete else 'pending'}"
