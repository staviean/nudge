"""Data models for the Nudge integration.

These dataclasses are the source of truth for all rich task metadata that the
native Home Assistant TodoItem cannot represent (categories, colors, icons,
subtasks, durations, nag configuration, frequency, notification routing, IFTTT).

Everything is plain/serializable so it can be persisted via helpers.storage.Store.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, time, timedelta
from typing import Any
import uuid

from .const import Frequency, NotificationType, TaskStatus


def _new_id() -> str:
    """Short unique id used for tasks/categories/subtasks."""
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Serialization helpers — datetimes/dates are stored as ISO strings.
# ---------------------------------------------------------------------------
def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    # Accept both date and datetime-ish strings.
    try:
        return date.fromisoformat(value)
    except ValueError:
        return datetime.fromisoformat(value).date()


@dataclass
class Subtask:
    """A child item of a Task."""

    summary: str
    done: bool = False
    uid: str = field(default_factory=_new_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Subtask":
        return cls(
            summary=data["summary"],
            done=bool(data.get("done", False)),
            uid=data.get("uid", _new_id()),
        )


@dataclass
class Category:
    """A grouping of tasks. Surfaces as one todo entity."""

    name: str
    color: str | None = None          # hex e.g. "#E91E63"
    icon: str | None = None           # mdi icon e.g. "mdi:broom"
    uid: str = field(default_factory=_new_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Category":
        return cls(
            name=data["name"],
            color=data.get("color"),
            icon=data.get("icon"),
            uid=data.get("uid", _new_id()),
        )


@dataclass
class Task:
    """A full task with all Nudge metadata."""

    summary: str
    category_id: str | None = None
    description: str | None = None

    # Scheduling
    due: datetime | None = None              # when it's due (start of attention)
    end: datetime | None = None              # hard end / deadline
    duration_minutes: int | None = None      # estimated time to complete

    # Repetition
    frequency: Frequency = Frequency.NONE

    # Notification + nag config
    notification_type: NotificationType = NotificationType.NONE
    notify_service: str | None = None        # override default notify target
    nag_enabled: bool = False
    nag_interval_minutes: int | None = None  # None -> use integration default
    quiet_hours_override: bool = False       # if True, this task ignores quiet hours

    # IFTTT
    ifttt_event: str | None = None           # IFTTT webhook event name to fire

    # State
    status: TaskStatus = TaskStatus.NEEDS_ACTION
    subtasks: list[Subtask] = field(default_factory=list)

    # Runtime nag bookkeeping (persisted so restarts don't reset progress)
    last_nag: datetime | None = None
    snooze_count: int = 0
    snoozed_until: datetime | None = None

    uid: str = field(default_factory=_new_id)
    created: datetime = field(default_factory=datetime.now)

    # ----- serialization ---------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "category_id": self.category_id,
            "description": self.description,
            "due": _iso(self.due),
            "end": _iso(self.end),
            "duration_minutes": self.duration_minutes,
            "frequency": str(self.frequency),
            "notification_type": str(self.notification_type),
            "notify_service": self.notify_service,
            "nag_enabled": self.nag_enabled,
            "nag_interval_minutes": self.nag_interval_minutes,
            "quiet_hours_override": self.quiet_hours_override,
            "ifttt_event": self.ifttt_event,
            "status": str(self.status),
            "subtasks": [s.to_dict() for s in self.subtasks],
            "last_nag": _iso(self.last_nag),
            "snooze_count": self.snooze_count,
            "snoozed_until": _iso(self.snoozed_until),
            "uid": self.uid,
            "created": _iso(self.created),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            summary=data["summary"],
            category_id=data.get("category_id"),
            description=data.get("description"),
            due=_parse_dt(data.get("due")),
            end=_parse_dt(data.get("end")),
            duration_minutes=data.get("duration_minutes"),
            frequency=Frequency(data.get("frequency", Frequency.NONE)),
            notification_type=NotificationType(
                data.get("notification_type", NotificationType.NONE)
            ),
            notify_service=data.get("notify_service"),
            nag_enabled=bool(data.get("nag_enabled", False)),
            nag_interval_minutes=data.get("nag_interval_minutes"),
            quiet_hours_override=bool(data.get("quiet_hours_override", False)),
            ifttt_event=data.get("ifttt_event"),
            status=TaskStatus(data.get("status", TaskStatus.NEEDS_ACTION)),
            subtasks=[Subtask.from_dict(s) for s in data.get("subtasks", [])],
            last_nag=_parse_dt(data.get("last_nag")),
            snooze_count=int(data.get("snooze_count", 0)),
            snoozed_until=_parse_dt(data.get("snoozed_until")),
            uid=data.get("uid", _new_id()),
            created=_parse_dt(data.get("created")) or datetime.now(),
        )

    # ----- behavior helpers ------------------------------------------------
    def next_occurrence(self, from_dt: datetime) -> datetime | None:
        """Compute the next due datetime for a repeating task."""
        if self.due is None:
            return None
        if self.frequency is Frequency.DAILY:
            return self.due + timedelta(days=1)
        if self.frequency is Frequency.WEEKLY:
            return self.due + timedelta(weeks=1)
        if self.frequency is Frequency.MONTHLY:
            # Naive month roll; refined in the scheduler chunk.
            month = self.due.month % 12 + 1
            year = self.due.year + (1 if self.due.month == 12 else 0)
            day = min(self.due.day, 28)
            return self.due.replace(year=year, month=month, day=day)
        if self.frequency is Frequency.YEARLY:
            return self.due.replace(year=self.due.year + 1)
        return None
