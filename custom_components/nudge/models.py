"""Data models for the Nudge integration.

These dataclasses are the source of truth for all rich task metadata that the
native Home Assistant TodoItem cannot represent (categories, colors, icons,
subtasks, durations, nag configuration, frequency, notification routing, IFTTT).

Everything is plain/serializable so it can be persisted via helpers.storage.Store.
"""

from __future__ import annotations

import calendar
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


def _add_months(dt: datetime, months: int) -> datetime:
    """Return *dt* shifted by *months*, clamping the day to the target month's
    last valid day (so Jan 31 + 1 month -> Feb 28/29, never an overflow)."""
    total = dt.year * 12 + (dt.month - 1) + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    last_day = calendar.monthrange(year, month)[1]
    return dt.replace(year=year, month=month, day=min(dt.day, last_day))


@dataclass
class Subtask:
    """A child item of a Task."""

    summary: str
    done: bool = False
    announcement_message: str | None = None  # optional custom TTS text for this subtask
    uid: str = field(default_factory=_new_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Subtask":
        return cls(
            summary=data["summary"],
            done=bool(data.get("done", False)),
            announcement_message=data.get("announcement_message"),
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
    interval: int = 1                        # "every N" multiplier (every 3 days/hours/weeks)
    weekdays: list[int] = field(default_factory=list)  # WEEKLY: 0=Mon..6=Sun; [] = plain weekly

    # Notification + nag config
    notification_type: NotificationType = NotificationType.NONE
    notify_targets: list[str] = field(default_factory=list)  # devices/services; [] = use default
    announcement_message: str | None = None  # custom TTS/announce text (overrides default)
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
            "interval": self.interval,
            "weekdays": list(self.weekdays),
            "notification_type": str(self.notification_type),
            "notify_targets": list(self.notify_targets),
            "announcement_message": self.announcement_message,
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
            interval=int(data.get("interval", 1) or 1),
            weekdays=[int(d) for d in data.get("weekdays", [])],
            notification_type=NotificationType(
                data.get("notification_type", NotificationType.NONE)
            ),
            notify_targets=(
                data.get("notify_targets")
                or ([data["notify_service"]] if data.get("notify_service") else [])
            ),
            announcement_message=data.get("announcement_message"),
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
        """Return the next due datetime strictly after *from_dt*.

        The recurrence is anchored to the original ``due`` time-of-day. The
        result is always advanced at least one period beyond ``due`` (so a task
        never re-schedules onto its current slot) and strictly past ``from_dt``
        (so an overdue task jumps to the next *future* slot instead of
        re-nagging in the past).
        """
        if self.due is None or self.frequency is Frequency.NONE:
            return None

        due = self.due
        interval = self.interval if self.interval and self.interval > 0 else 1

        if self.frequency is Frequency.HOURLY:
            return self._advance_fixed(timedelta(hours=interval), from_dt)
        if self.frequency is Frequency.DAILY:
            return self._advance_fixed(timedelta(days=interval), from_dt)
        if self.frequency is Frequency.WEEKLY:
            if self.weekdays:
                return self._next_weekday_occurrence(from_dt, interval)
            return self._advance_fixed(timedelta(weeks=interval), from_dt)
        if self.frequency is Frequency.MONTHLY:
            k = 1
            nxt = _add_months(due, interval)
            while nxt <= from_dt:
                k += 1
                nxt = _add_months(due, interval * k)
            return nxt
        if self.frequency is Frequency.YEARLY:
            k = 1
            nxt = _add_months(due, 12 * interval)
            while nxt <= from_dt:
                k += 1
                nxt = _add_months(due, 12 * interval * k)
            return nxt
        return None

    def _advance_fixed(self, step: timedelta, from_dt: datetime) -> datetime:
        """Advance ``due`` by whole ``step``s until strictly past both ``due``
        (at least one step) and ``from_dt``."""
        nxt = self.due + step
        while nxt <= from_dt:
            nxt += step
        return nxt

    def _next_weekday_occurrence(
        self, from_dt: datetime, interval: int
    ) -> datetime | None:
        """Next occurrence for WEEKLY recurrence restricted to ``weekdays``.

        Scans forward day by day for the first selected weekday, at ``due``'s
        time-of-day, on a week that is an ``interval`` multiple from the due
        week, and strictly after both ``due`` and ``from_dt``.
        """
        due = self.due
        latest = max(due, from_dt)
        tod = due.time()
        anchor_monday = due.date() - timedelta(days=due.weekday())
        day = latest.date()
        for _ in range(372):  # > 53 weeks; guaranteed to find a match
            candidate = datetime.combine(day, tod)
            if candidate > latest and candidate.weekday() in self.weekdays:
                cand_monday = candidate.date() - timedelta(days=candidate.weekday())
                weeks_since = (cand_monday - anchor_monday).days // 7
                if weeks_since >= 0 and weeks_since % interval == 0:
                    return candidate
            day += timedelta(days=1)
        return None
