"""Record of the MQTT topics the compat publisher last wrote, per dashboard kind.

The compat publisher rebuilds the full set of sensors on every run. To retire an
entity that no longer exists (a deleted account, a dropped utility series) it has
to know what it published last time so it can empty that entity's config topic.
This table is that memory; it survives restarts, unlike an in process set.
"""
from __future__ import annotations

import json

from .db import connect


async def get_mqtt_topics(kind: str) -> list[dict]:
    """Topics published for ``kind`` on the previous run.

    Each entry is ``{"config_topic": str, "state_topics": list[str]}``.
    """
    async with connect() as db:
        cursor = await db.execute(
            "SELECT config_topic, state_topics FROM mqtt_topics WHERE kind=?", (kind,)
        )
        rows = await cursor.fetchall()
    return [
        {"config_topic": config_topic, "state_topics": json.loads(state_topics or "[]")}
        for config_topic, state_topics in rows
    ]


async def set_mqtt_topics(kind: str, entries: list[dict]) -> None:
    """Replace the recorded topics for ``kind`` with the current run's set."""
    async with connect() as db:
        await db.execute("DELETE FROM mqtt_topics WHERE kind=?", (kind,))
        await db.executemany(
            "INSERT INTO mqtt_topics (kind, config_topic, state_topics) VALUES (?, ?, ?)",
            [
                (kind, entry["config_topic"], json.dumps(entry["state_topics"]))
                for entry in entries
            ],
        )
        await db.commit()
