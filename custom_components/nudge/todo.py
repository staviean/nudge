"""To-do list platform for Nudge.

Each Nudge category is surfaced as a native Home Assistant TodoListEntity, so
tasks remain visible and manageable from the standard To-do dashboard card even
before the custom Nudge card is installed. The rich metadata (nag config,
subtasks, frequency, etc.) lives in the Nudge store; this platform projects the
subset that the native TodoItem can represent (summary, status, due, description).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_STORE_UPDATED, TaskStatus
from .models import Category, Task

if TYPE_CHECKING:
    from . import NudgeConfigEntry
    from .store import NudgeStore

# Uncategorized tasks are collected under a synthetic list.
UNCATEGORIZED_ID = "uncategorized"

SUPPORTED_FEATURES = (
    TodoListEntityFeature.CREATE_TODO_ITEM
    | TodoListEntityFeature.UPDATE_TODO_ITEM
    | TodoListEntityFeature.DELETE_TODO_ITEM
    | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
    | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: "NudgeConfigEntry",
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nudge to-do list entities from a config entry."""
    store = entry.runtime_data.store

    known: set[str] = set()

    @callback
    def _sync_entities() -> None:
        """Create entities for any categories that don't yet have one."""
        new_entities: list[NudgeTodoListEntity] = []

        # Synthetic "Uncategorized" list, always present.
        if UNCATEGORIZED_ID not in known:
            known.add(UNCATEGORIZED_ID)
            new_entities.append(
                NudgeTodoListEntity(store, category_id=None, name="Nudge: Uncategorized")
            )

        for cat in store.categories.values():
            if cat.uid not in known:
                known.add(cat.uid)
                new_entities.append(
                    NudgeTodoListEntity(store, category_id=cat.uid, name=f"Nudge: {cat.name}")
                )

        if new_entities:
            async_add_entities(new_entities)

    _sync_entities()

    # When the store changes (e.g. a new category), add entities as needed.
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_STORE_UPDATED, _sync_entities)
    )


class NudgeTodoListEntity(TodoListEntity):
    """A to-do list backed by one Nudge category."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(
        self, store: "NudgeStore", category_id: str | None, name: str
    ) -> None:
        self._store = store
        self._category_id = category_id
        self._attr_name = name
        # Stable unique_id so entity survives restarts.
        self._attr_unique_id = f"{DOMAIN}_{category_id or UNCATEGORIZED_ID}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to store updates so the list refreshes live."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STORE_UPDATED, self._handle_store_update
            )
        )

    @callback
    def _handle_store_update(self) -> None:
        self.async_write_ha_state()

    # ----- projection: Nudge Task -> native TodoItem ----------------------
    @property
    def todo_items(self) -> list[TodoItem]:
        items: list[TodoItem] = []
        for task in self._store.tasks_in_category(self._category_id):
            status = (
                TodoItemStatus.COMPLETED
                if task.status is TaskStatus.COMPLETED
                else TodoItemStatus.NEEDS_ACTION
            )
            items.append(
                TodoItem(
                    summary=task.summary,
                    uid=task.uid,
                    status=status,
                    due=task.due,
                    description=task.description,
                )
            )
        return items

    # ----- native actions write back into the Nudge store -----------------
    async def async_create_todo_item(self, item: TodoItem) -> None:
        task = Task(
            summary=item.summary or "Untitled",
            category_id=self._category_id,
            description=item.description,
            due=item.due if isinstance(item.due, datetime) else None,
        )
        await self._store.add_task(task)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        changes: dict = {}
        if item.summary is not None:
            changes["summary"] = item.summary
        if item.description is not None:
            changes["description"] = item.description
        if isinstance(item.due, datetime):
            changes["due"] = item.due
        if item.status is not None:
            changes["status"] = (
                TaskStatus.COMPLETED
                if item.status == TodoItemStatus.COMPLETED
                else TaskStatus.NEEDS_ACTION
            )
        if item.uid:
            await self._store.update_task(item.uid, **changes)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self._store.delete_task(uid)