"""Nag engine for the Nudge integration.

A 60-second background timer loop that evaluates every nag-enabled, incomplete
task and fires push notifications and/or TTS announcements. Listens for
mobile_app_notification_action events so the user can complete, snooze, or
push-to-next directly from the lock screen.

Design notes
------------
* Quiet hours are evaluated against naive local time; the window may cross
  midnight (e.g. 22:00 → 07:00).
* Per-task ``nag_interval_minutes`` overrides the integration default.
* Actionable notification actions embed the task UID in the action string
  (e.g. ``nudge_complete_abc123``) so we can route the response without
  keeping per-device state.
* All datetimes stored on Task are naive local; we strip tzinfo from the
  HA-provided UTC datetime before any comparisons.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .const import (
    ACTION_COMPLETE,
    ACTION_PUSH_NEXT,
    ACTION_SNOOZE,
    CONF_DEFAULT_NOTIFY,
    CONF_NAG_INTERVAL,
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_SNOOZE_CAP,
    CONF_TTS_ENGINE,
    CONF_TTS_MEDIA_PLAYER,
    DEFAULT_NAG_INTERVAL_MIN,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DEFAULT_SNOOZE_CAP,
    EVENT_MOBILE_ACTION,
    NAG_TICK_SECONDS,
    NotificationType,
    TaskStatus,
)
from .models import Task

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .store import NudgeStore

_LOGGER = logging.getLogger(__name__)


class NagEngine:
    """Background nag engine — one instance per config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        store: NudgeStore,
        entry: ConfigEntry,
    ) -> None:
        self.hass = hass
        self.store = store
        self.entry = entry
        self._unsub_timer = None
        self._unsub_event = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_start(self) -> None:
        """Register the tick timer and the mobile-action event listener."""
        self._unsub_timer = async_track_time_interval(
            self.hass,
            self._async_tick,
            timedelta(seconds=NAG_TICK_SECONDS),
        )
        self._unsub_event = self.hass.bus.async_listen(
            EVENT_MOBILE_ACTION, self._async_handle_mobile_action
        )
        _LOGGER.debug("Nag engine started (tick=%ds)", NAG_TICK_SECONDS)

    async def async_stop(self) -> None:
        """Cancel the tick timer and event listener."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_event:
            self._unsub_event()
            self._unsub_event = None
        _LOGGER.debug("Nag engine stopped")

    # ------------------------------------------------------------------
    # Options helpers (read live so changes take effect immediately)
    # ------------------------------------------------------------------

    @property
    def _opts(self) -> dict:
        return self.entry.options

    @property
    def _default_notify(self) -> str | None:
        val = self._opts.get(CONF_DEFAULT_NOTIFY, "")
        return val if val else None

    @property
    def _tts_engine(self) -> str:
        return self._opts.get(CONF_TTS_ENGINE, "tts.home_assistant_cloud")

    @property
    def _tts_player(self) -> str | None:
        val = self._opts.get(CONF_TTS_MEDIA_PLAYER, "")
        return val if val else None

    @property
    def _nag_interval(self) -> int:
        return int(self._opts.get(CONF_NAG_INTERVAL, DEFAULT_NAG_INTERVAL_MIN))

    @property
    def _snooze_cap(self) -> int:
        return int(self._opts.get(CONF_SNOOZE_CAP, DEFAULT_SNOOZE_CAP))

    @property
    def _quiet_start(self) -> str:
        return self._opts.get(CONF_QUIET_START, DEFAULT_QUIET_START)

    @property
    def _quiet_end(self) -> str:
        return self._opts.get(CONF_QUIET_END, DEFAULT_QUIET_END)

    # ------------------------------------------------------------------
    # Quiet hours
    # ------------------------------------------------------------------

    @staticmethod
    def _to_naive_local(dt: datetime | None) -> datetime | None:
        """Normalise any datetime to naive local time for safe comparison.

        Task datetimes may be timezone-aware UTC (when set via cv.datetime in a
        service call) or naive local (when written directly by the engine).
        Always strip tzinfo after converting so comparisons never raise TypeError.
        """
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt_util.as_local(dt).replace(tzinfo=None)
        return dt

    def _is_quiet_hours(self, now: datetime) -> bool:
        """Return True if *now* falls inside the configured quiet window.

        Handles windows that cross midnight (e.g. 22:00 → 07:00).
        """
        try:
            qs_h, qs_m = (int(x) for x in self._quiet_start.split(":"))
            qe_h, qe_m = (int(x) for x in self._quiet_end.split(":"))
        except (ValueError, AttributeError):
            _LOGGER.warning(
                "Invalid quiet hours format: start=%s end=%s",
                self._quiet_start,
                self._quiet_end,
            )
            return False

        current = time(now.hour, now.minute)
        start = time(qs_h, qs_m)
        end = time(qe_h, qe_m)

        if start == end:
            return False  # no window configured

        if start > end:
            # Crosses midnight: quiet from start→23:59 OR 00:00→end
            return current >= start or current < end
        return start <= current < end

    # ------------------------------------------------------------------
    # Nag eligibility
    # ------------------------------------------------------------------

    def _task_needs_nag(self, task: Task, now: datetime) -> bool:
        """Return True if *task* should fire a nag at *now*."""
        if task.status != TaskStatus.NEEDS_ACTION:
            return False
        if not task.nag_enabled:
            return False
        if task.notification_type is NotificationType.NONE:
            return False

        # Normalise task datetimes to naive local so comparisons never raise
        # TypeError (cv.datetime produces UTC-aware datetimes; our store may
        # also hold naive local values written by the engine itself).
        due = self._to_naive_local(task.due)
        snoozed_until = self._to_naive_local(task.snoozed_until)
        last_nag = self._to_naive_local(task.last_nag)

        # Only nag once the task is due.
        if due is None or now < due:
            return False

        # Honour quiet hours unless the task explicitly opts out.
        if not task.quiet_hours_override and self._is_quiet_hours(now):
            return False

        # Waiting out an explicit snooze.
        if snoozed_until and now < snoozed_until:
            return False

        # Snooze cap: 0 means unlimited.
        cap = self._snooze_cap
        if cap > 0 and task.snooze_count >= cap:
            _LOGGER.debug(
                "Task '%s' hit snooze cap (%d); suppressing nag", task.summary, cap
            )
            return False

        # Interval guard: don't re-nag before the interval has elapsed.
        interval_min = task.nag_interval_minutes or self._nag_interval
        if last_nag is not None:
            if now < last_nag + timedelta(minutes=interval_min):
                return False

        return True

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    async def _async_tick(self, now: datetime) -> None:
        """Called every NAG_TICK_SECONDS by async_track_time_interval.

        ``now`` is UTC-aware; convert to naive local before comparisons.
        """
        local_now = dt_util.as_local(now).replace(tzinfo=None)

        for task in list(self.store.tasks.values()):
            if not self._task_needs_nag(task, local_now):
                continue
            try:
                await self._async_fire_nag(task, local_now)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error firing nag for task '%s'", task.summary)

    # ------------------------------------------------------------------
    # Notification dispatch
    # ------------------------------------------------------------------

    async def _async_fire_nag(self, task: Task, now: datetime) -> None:
        """Send notifications for *task* and update bookkeeping."""
        ntype = task.notification_type

        if ntype in (NotificationType.PUSH, NotificationType.BOTH):
            await self._async_push(task)

        if ntype in (NotificationType.ANNOUNCE, NotificationType.BOTH):
            await self._async_announce(task)

        task.last_nag = now
        await self.store.async_save()
        _LOGGER.info("Nagged task '%s' (%s)", task.summary, task.uid)

    async def _async_push(self, task: Task) -> None:
        """Send an actionable push notification.

        Strategy:
        1. Call the notify entity's ``async_send_message`` method directly.
           This bypasses the strict ``notify.send_message`` service schema (which only
           allows message + title) and lets the companion app receive the full ``data``
           dict including action buttons and tag.
        2. Fall back to ``notify.send_message`` if the entity cannot be found.
        """
        notify_entity = task.notify_service or self._default_notify
        if not notify_entity:
            _LOGGER.warning(
                "Task '%s' wants push notification but no notify entity is configured. "
                "Set 'default_notify_service' in Nudge options.",
                task.summary,
            )
            return

        due_local = self._to_naive_local(task.due)
        due_str = due_local.strftime("%a %d %b, %I:%M %p") if due_local else "now"
        body = task.summary
        if task.description:
            body += f"\n{task.description}"
        title = f"Nudge — due {due_str}"

        # Actionable buttons embedded in the notification.
        mobile_data = {
            "tag": task.uid,  # collapse previous notification for same task
            "persistent": False,
            "actions": [
                {"action": f"{ACTION_COMPLETE}_{task.uid}", "title": "Done"},
                {"action": f"{ACTION_SNOOZE}_{task.uid}", "title": "Snooze"},
                {"action": f"{ACTION_PUSH_NEXT}_{task.uid}", "title": "Next time"},
            ],
        }

        # Route based on whether the configured value is an entity or a legacy service.
        #
        # - Entity (e.g. notify.device_evol_otr): use notify.send_message with target.
        #   The entity-based schema only allows message + title — no data/actions.
        # - Legacy service (e.g. notify.mobile_app_evol_otr): call it directly.
        #   Legacy services accept a full data dict including action buttons.
        #
        # To get Done/Snooze/Next time buttons, configure notify_service to the
        # legacy service name (Developer Tools → Actions → search notify.mobile_app_*).
        from homeassistant.helpers import entity_registry as er

        entity_reg = er.async_get(self.hass)
        is_entity = entity_reg.async_get(notify_entity) is not None

        if is_entity:
            _LOGGER.info(
                "Nudge push: '%s' is an entity — sending plain notification "
                "(no action buttons). Set notify_service to a legacy service "
                "like notify.mobile_app_* to enable buttons.",
                notify_entity,
            )
            await self.hass.services.async_call(
                "notify",
                "send_message",
                service_data={"message": body, "title": title},
                target={"entity_id": notify_entity},
            )
        else:
            # Treat as a legacy service — call it directly with the full data dict.
            domain, svc_name = notify_entity.split(".", 1)
            _LOGGER.info(
                "Nudge push: '%s' is a legacy service — sending actionable notification",
                notify_entity,
            )
            await self.hass.services.async_call(
                domain,
                svc_name,
                {"message": body, "title": title, "data": mobile_data},
            )

    async def _async_announce(self, task: Task) -> None:
        """Fire a TTS announcement on the configured media player."""
        tts_player = self._tts_player
        if not tts_player:
            _LOGGER.warning(
                "Task '%s' wants TTS announcement but no media_player is configured. "
                "Set 'tts_media_player' in Nudge options.",
                task.summary,
            )
            return

        if task.announcement_message:
            message = task.announcement_message
        else:
            message = f"Nudge reminder: {task.summary}."
            if task.description:
                message += f" {task.description}."

        # Append any incomplete subtasks that carry their own announcement.
        for sub in task.subtasks:
            if not sub.done and sub.announcement_message:
                message += f" {sub.announcement_message}"

        await self.hass.services.async_call(
            "tts",
            "speak",
            {
                "entity_id": self._tts_engine,
                "media_player_entity_id": tts_player,
                "message": message,
            },
        )

    # ------------------------------------------------------------------
    # Mobile action handler
    # ------------------------------------------------------------------

    @callback
    def _async_handle_mobile_action(self, event: Event) -> None:
        """Route mobile_app_notification_action events to the right handler.

        Action strings are in the form ``{ACTION_PREFIX}_{task_uid}``.
        """
        action: str = event.data.get("action", "")

        if action.startswith(ACTION_COMPLETE + "_"):
            uid = action[len(ACTION_COMPLETE) + 1:]
            self.hass.async_create_task(self._handle_complete(uid))
        elif action.startswith(ACTION_SNOOZE + "_"):
            uid = action[len(ACTION_SNOOZE) + 1:]
            self.hass.async_create_task(self._handle_snooze(uid))
        elif action.startswith(ACTION_PUSH_NEXT + "_"):
            uid = action[len(ACTION_PUSH_NEXT) + 1:]
            self.hass.async_create_task(self._handle_push_next(uid))
        # Ignore unrelated actions silently.

    async def _handle_complete(self, uid: str) -> None:
        task = self.store.tasks.get(uid)
        if task is None:
            _LOGGER.debug("Mobile action: complete for unknown task %s", uid)
            return
        await self.store.complete_task(uid)
        _LOGGER.info("Task '%s' completed via mobile notification action", task.summary)

    async def _handle_snooze(self, uid: str) -> None:
        task = self.store.tasks.get(uid)
        if task is None:
            _LOGGER.debug("Mobile action: snooze for unknown task %s", uid)
            return
        snooze_min = task.nag_interval_minutes or self._nag_interval
        task.snoozed_until = datetime.now() + timedelta(minutes=snooze_min)
        task.snooze_count += 1
        await self.store.async_save()
        _LOGGER.info(
            "Task '%s' snoozed %d min via mobile notification action",
            task.summary,
            snooze_min,
        )

    async def _handle_push_next(self, uid: str) -> None:
        task = self.store.tasks.get(uid)
        if task is None:
            _LOGGER.debug("Mobile action: push_next for unknown task %s", uid)
            return
        nxt = task.next_occurrence(datetime.now())
        if nxt is not None:
            task.due = nxt
            task.snooze_count = 0
            task.snoozed_until = None
            task.last_nag = None
            await self.store.async_save()
            _LOGGER.info(
                "Task '%s' pushed to next occurrence (%s) via mobile action",
                task.summary,
                nxt.isoformat(),
            )
        else:
            _LOGGER.debug(
                "Task '%s' has no next occurrence; push_next is a no-op", task.summary
            )
