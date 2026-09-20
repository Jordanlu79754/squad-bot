"""Small JSON-backed store for "what have I already seen?".

The bot needs to remember two things across restarts: which patch notes it has
already announced, and a short history of Major Order progress so it can work
out how fast the war is actually moving.

Writes go to a temp file and then get renamed over the real one, so a crash
mid-write leaves the previous state intact rather than a half-written file.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MAX_SAMPLES = 96  # at one sample per 15 min, roughly a day of history


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class State:
    def __init__(self, path: str | os.PathLike = "bot_state.json"):
        self.path = Path(path)
        self._data: dict = {"seen_patches": {}, "order_samples": {}}
        self.load()

    # ------------------------------------------------------------ persistence

    def load(self) -> None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return
        if isinstance(loaded, dict):
            self._data.update(loaded)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent,
            prefix=self.path.name, suffix=".tmp", delete=False,
        )
        try:
            with handle:
                json.dump(self._data, handle, indent=1)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(handle.name, self.path)
        except BaseException:
            Path(handle.name).unlink(missing_ok=True)
            raise

    # --------------------------------------------------------- patch tracking

    def is_patch_seen(self, game: str, url: str) -> bool:
        return url in self._data["seen_patches"].get(game, [])

    def mark_patch_seen(self, game: str, url: str) -> None:
        seen = self._data["seen_patches"].setdefault(game, [])
        if url not in seen:
            seen.append(url)
            del seen[:-40]  # only the recent ones matter

    def has_seen_any(self, game: str) -> bool:
        """True once this game has been polled at least once.

        On the very first run every patch note looks new, and announcing a
        year of back-catalogue into a channel is not what anyone wants. The
        first poll records them silently instead.
        """
        return bool(self._data["seen_patches"].get(game))

    # ---------------------------------------------------- major order history

    def record_order_sample(self, order_id: int, progress: list[int]) -> None:
        samples = self._data["order_samples"].setdefault(str(order_id), [])
        samples.append([utcnow().isoformat(), list(progress)])
        del samples[:-MAX_SAMPLES]
        # Old orders are finished; there is no reason to keep their history.
        for key in list(self._data["order_samples"]):
            if key != str(order_id):
                del self._data["order_samples"][key]

    def progress_rate(self, order_id: int, task_index: int) -> float | None:
        """Progress per second on one task, from the oldest sample we hold.

        Returns None until there are two samples far enough apart to mean
        anything -- a rate computed over 30 seconds is noise, not a trend.
        """
        samples = self._data["order_samples"].get(str(order_id), [])
        if len(samples) < 2:
            return None

        first_time, first_progress = samples[0]
        last_time, last_progress = samples[-1]
        if task_index >= len(first_progress) or task_index >= len(last_progress):
            return None

        elapsed = (
            datetime.fromisoformat(last_time) - datetime.fromisoformat(first_time)
        ).total_seconds()
        if elapsed < 600:
            return None

        return (last_progress[task_index] - first_progress[task_index]) / elapsed
