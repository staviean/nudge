"""Persistence layer for Nudge.

Wraps homeassistant.helpers.storage.Store to keep all categories and tasks on
disk as JSON. This is the single source of truth; the todo entities and the
custom card are both projections of this data.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    SIGNAL_STORE_UPDATED,
    STORAGE_KEY,
    STORAGE_VERSION,
    STORAGE_MINOR_VERSION,
    TaskStatus,
)
from .models import Category, Subtask, Task

_LOGGER = logging.getLogger(__name__)


class NudgeStore:
    """Async data store for Nudge categories and tasks."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            minor_version=STORAGE_MINOR_VERSION,
        )
        self.categories: dict[str, Category] = {}
        self.tasks: dict[str, Task] = {}

    # ----- lifecycle -------------------------------------------------------
    async def async_load(self) -> None:
        """Load data from disk into memory."""
        data = await self._store.async_load()
        if not data:
            _LOGGER.debug("No existing Nudge data; starting fresh")
            return
        self.categories = {
            c["uid"]: Category.from_dict(c) for c in data.get("categories", [])
        }
        self.tasks = {
            t["uid"]: Task.from_dict(t) for t in data.get("tasks", [])
        }
        _LOGGER.debug(
            "Loaded %d categories, %d tasks",
            len(self.categories),
            len(self.tasks),
        )

    async def async_save(self) -> None:
        """Persist current in-memory data and notify listeners."""
        await self._store.async_save(
            {
                "categories": [c.to_dict() for c in self.categories.values()],
                "tasks": [t.to_dict() for t in self.tasks.values()],
            }
        )
        async_dispatcher_send(self.hass, SIGNAL_STORE_UPDATED)

    # ----- category CRUD ---------------------------------------------------
    async def add_category(self, category: Category) -> Category:
        self.categories[category.uid] = category
        await self.async_save()
        return category

    async def update_category(self, uid: str, **changes: Any) -> Category | None:
        cat = self.categories.get(uid)
        if cat is None:
            return None
        for key, value in changes.items():
            if value is not None and hasattr(cat, key):
                setattr(cat, key, value)
        await self.async_save()
        return cat

    async def delete_category(self, uid: str, reassign_to: str | None = None) -> bool:
        if uid not in self.categories:
            return False
        # Re-home or orphan tasks in this category.
        for task in self.tasks.values():
            if task.category_id == uid:
                task.category_id = reassign_to
        del self.categories[uid]
        await self.async_save()
        return True

    # ----- task CRUD -------------------------------------------------------
    async def add_task(self, task: Task) -> Task:
        self.tasks[task.uid] = task
        await self.async_save()
        return task

    async def update_task(self, uid: str, **changes: Any) -> Task | None:
        task = self.tasks.get(uid)
        if task is None:
            return None
        for key, value in changes.items():
            if value is not None and hasattr(task, key):
                setattr(task, key, value)
        await self.async_save()
        return task

    async def delete_task(self, uid: str) -> bool:
        if uid not in self.tasks:
            return False
        del self.tasks[uid]
        await self.async_save()
        return True

    async def complete_task(self, uid: str) -> Task | None:
        task = self.tasks.get(uid)
        if task is None:
            return None
        # Repeating tasks roll forward instead of closing out.
        nxt = task.next_occurrence(datetime.now())
        if nxt is not None:
            task.due = nxt
            task.status = TaskStatus.NEEDS_ACTION
            task.snooze_count = 0
            task.snoozed_until = None
            task.last_nag = None
            for sub in task.subtasks:
                sub.done = False
        else:
            task.status = TaskStatus.COMPLETED
        await self.async_save()
        return task

    # ----- subtask helpers -------------------------------------------------
    async def add_subtask(self, task_uid: str, summary: str) -> Subtask | None:
        task = self.tasks.get(task_uid)
        if task is None:
            return None
        sub = Subtask(summary=summary)
        task.subtasks.append(sub)
        await self.async_save()
        return sub

    async def toggle_subtask(self, task_uid: str, subtask_uid: str) -> bool:
        task = self.tasks.get(task_uid)
        if task is None:
            return False
        for sub in task.subtasks:
            if sub.uid == subtask_uid:
                sub.done = not sub.done
                await self.async_save()
                return True
        return False

    # ----- queries ---------------------------------------------------------
    def tasks_in_category(self, category_id: str | None) -> list[Task]:
        return [t for t in self.tasks.values() if t.category_id == category_id]
