"""Service registration for Nudge.

Exposes the full action surface as `nudge.*` services so everything can be driven
from the UI (Developer Tools -> Actions), automations, or the custom card:
task CRUD, complete/snooze/push-to-next, subtasks, and category CRUD.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    Frequency,
    NotificationType,
    SERVICE_ADD_SUBTASK,
    SERVICE_COMPLETE_TASK,
    SERVICE_CREATE_CATEGORY,
    SERVICE_CREATE_TASK,
    SERVICE_DELETE_CATEGORY,
    SERVICE_DELETE_TASK,
    SERVICE_EDIT_CATEGORY,
    SERVICE_EDIT_TASK,
    SERVICE_PUSH_NEXT,
    SERVICE_SNOOZE_TASK,
    SERVICE_TOGGLE_SUBTASK,
)
from .models import Category, Task

if TYPE_CHECKING:
    from .store import NudgeStore

_LOGGER = logging.getLogger(__name__)

_ALL_SERVICES = [
    SERVICE_CREATE_TASK,
    SERVICE_EDIT_TASK,
    SERVICE_DELETE_TASK,
    SERVICE_COMPLETE_TASK,
    SERVICE_SNOOZE_TASK,
    SERVICE_PUSH_NEXT,
    SERVICE_ADD_SUBTASK,
    SERVICE_TOGGLE_SUBTASK,
    SERVICE_CREATE_CATEGORY,
    SERVICE_EDIT_CATEGORY,
    SERVICE_DELETE_CATEGORY,
]

# --- Schemas ---------------------------------------------------------------
CREATE_TASK_SCHEMA = vol.Schema(
    {
        vol.Required("summary"): cv.string,
        vol.Optional("category_id"): cv.string,
        vol.Optional("description"): cv.string,
        vol.Optional("due"): cv.datetime,
        vol.Optional("end"): cv.datetime,
        vol.Optional("duration_minutes"): vol.All(int, vol.Range(min=0)),
        vol.Optional("frequency"): vol.In([f.value for f in Frequency]),
        vol.Optional("interval"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("weekdays"): [vol.All(vol.Coerce(int), vol.Range(min=0, max=6))],
        vol.Optional("notification_type"): vol.In([n.value for n in NotificationType]),
        vol.Optional("notify_targets"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("announcement_message"): cv.string,
        vol.Optional("nag_enabled"): cv.boolean,
        vol.Optional("nag_interval_minutes"): vol.All(int, vol.Range(min=1)),
        vol.Optional("quiet_hours_override"): cv.boolean,
        vol.Optional("ifttt_event"): cv.string,
    }
)

EDIT_TASK_SCHEMA = vol.Schema(
    {
        vol.Required("uid"): cv.string,
        vol.Optional("summary"): cv.string,
        vol.Optional("category_id"): cv.string,
        vol.Optional("description"): cv.string,
        vol.Optional("due"): cv.datetime,
        vol.Optional("end"): cv.datetime,
        vol.Optional("duration_minutes"): vol.All(int, vol.Range(min=0)),
        vol.Optional("frequency"): vol.In([f.value for f in Frequency]),
        vol.Optional("interval"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("weekdays"): [vol.All(vol.Coerce(int), vol.Range(min=0, max=6))],
        vol.Optional("notification_type"): vol.In([n.value for n in NotificationType]),
        vol.Optional("notify_targets"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("announcement_message"): cv.string,
        vol.Optional("nag_enabled"): cv.boolean,
        vol.Optional("nag_interval_minutes"): vol.All(int, vol.Range(min=1)),
        vol.Optional("quiet_hours_override"): cv.boolean,
        vol.Optional("ifttt_event"): cv.string,
    }
)

UID_SCHEMA = vol.Schema({vol.Required("uid"): cv.string})

SNOOZE_SCHEMA = vol.Schema(
    {
        vol.Required("uid"): cv.string,
        vol.Optional("minutes"): vol.All(int, vol.Range(min=1)),
    }
)

ADD_SUBTASK_SCHEMA = vol.Schema(
    {
        vol.Required("task_uid"): cv.string,
        vol.Required("summary"): cv.string,
        vol.Optional("announcement_message"): cv.string,
    }
)

TOGGLE_SUBTASK_SCHEMA = vol.Schema(
    {
        vol.Required("task_uid"): cv.string,
        vol.Required("subtask_uid"): cv.string,
    }
)

CREATE_CATEGORY_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Optional("color"): cv.string,
        vol.Optional("icon"): cv.string,
    }
)

EDIT_CATEGORY_SCHEMA = vol.Schema(
    {
        vol.Required("uid"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("color"): cv.string,
        vol.Optional("icon"): cv.string,
    }
)

DELETE_CATEGORY_SCHEMA = vol.Schema(
    {
        vol.Required("uid"): cv.string,
        vol.Optional("reassign_to"): cv.string,
    }
)


@callback
def async_register_services(hass: HomeAssistant, store: "NudgeStore") -> None:
    """Register all Nudge services with the current store instance.

    Always re-registers (no has_service guard) so that after an integration
    reload the handlers are bound to the fresh store rather than a stale one.
    """

    async def create_task(call: ServiceCall) -> None:
        d = call.data
        task = Task(
            summary=d["summary"],
            category_id=d.get("category_id"),
            description=d.get("description"),
            due=d.get("due"),
            end=d.get("end"),
            duration_minutes=d.get("duration_minutes"),
            frequency=Frequency(d.get("frequency", Frequency.NONE)),
            interval=d.get("interval", 1) or 1,
            weekdays=d.get("weekdays") or [],
            notification_type=NotificationType(
                d.get("notification_type", NotificationType.NONE)
            ),
            notify_targets=d.get("notify_targets") or [],
            announcement_message=d.get("announcement_message"),
            nag_enabled=d.get("nag_enabled", False),
            nag_interval_minutes=d.get("nag_interval_minutes"),
            quiet_hours_override=d.get("quiet_hours_override", False),
            ifttt_event=d.get("ifttt_event"),
        )
        await store.add_task(task)

    async def edit_task(call: ServiceCall) -> None:
        d = dict(call.data)
        uid = d.pop("uid")
        if "frequency" in d:
            d["frequency"] = Frequency(d["frequency"])
        if "notification_type" in d:
            d["notification_type"] = NotificationType(d["notification_type"])
        await store.update_task(uid, **d)

    async def delete_task(call: ServiceCall) -> None:
        await store.delete_task(call.data["uid"])

    async def complete_task(call: ServiceCall) -> None:
        await store.complete_task(call.data["uid"])

    async def snooze_task(call: ServiceCall) -> None:
        uid = call.data["uid"]
        task = store.tasks.get(uid)
        if task is None:
            return
        from datetime import timedelta

        minutes = call.data.get("minutes") or task.nag_interval_minutes or 30
        task.snoozed_until = datetime.now() + timedelta(minutes=minutes)
        task.snooze_count += 1
        await store.async_save()

    async def push_to_next(call: ServiceCall) -> None:
        uid = call.data["uid"]
        task = store.tasks.get(uid)
        if task is None:
            return
        nxt = task.next_occurrence(datetime.now())
        if nxt is not None:
            task.due = nxt
            task.snooze_count = 0
            task.snoozed_until = None
            task.last_nag = None
            await store.async_save()

    async def add_subtask(call: ServiceCall) -> None:
        await store.add_subtask(
            call.data["task_uid"],
            call.data["summary"],
            call.data.get("announcement_message"),
        )

    async def toggle_subtask(call: ServiceCall) -> None:
        await store.toggle_subtask(call.data["task_uid"], call.data["subtask_uid"])

    async def create_category(call: ServiceCall) -> None:
        cat = Category(
            name=call.data["name"],
            color=call.data.get("color"),
            icon=call.data.get("icon"),
        )
        await store.add_category(cat)

    async def edit_category(call: ServiceCall) -> None:
        d = dict(call.data)
        uid = d.pop("uid")
        await store.update_category(uid, **d)

    async def delete_category(call: ServiceCall) -> None:
        await store.delete_category(
            call.data["uid"], reassign_to=call.data.get("reassign_to")
        )

    services = [
        (SERVICE_CREATE_TASK, create_task, CREATE_TASK_SCHEMA),
        (SERVICE_EDIT_TASK, edit_task, EDIT_TASK_SCHEMA),
        (SERVICE_DELETE_TASK, delete_task, UID_SCHEMA),
        (SERVICE_COMPLETE_TASK, complete_task, UID_SCHEMA),
        (SERVICE_SNOOZE_TASK, snooze_task, SNOOZE_SCHEMA),
        (SERVICE_PUSH_NEXT, push_to_next, UID_SCHEMA),
        (SERVICE_ADD_SUBTASK, add_subtask, ADD_SUBTASK_SCHEMA),
        (SERVICE_TOGGLE_SUBTASK, toggle_subtask, TOGGLE_SUBTASK_SCHEMA),
        (SERVICE_CREATE_CATEGORY, create_category, CREATE_CATEGORY_SCHEMA),
        (SERVICE_EDIT_CATEGORY, edit_category, EDIT_CATEGORY_SCHEMA),
        (SERVICE_DELETE_CATEGORY, delete_category, DELETE_CATEGORY_SCHEMA),
    ]
    for name, handler, schema in services:
        hass.services.async_register(DOMAIN, name, handler, schema=schema)


@callback
def async_unregister_services(hass: HomeAssistant) -> None:
    """Remove all Nudge services. Called on entry unload so the next
    async_setup_entry re-registers handlers bound to a fresh store."""
    for name in _ALL_SERVICES:
        hass.services.async_remove(DOMAIN, name)
