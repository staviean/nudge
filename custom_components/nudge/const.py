"""Constants for the Nudge integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "nudge"

# --- Storage ---------------------------------------------------------------
STORAGE_KEY: Final = f"{DOMAIN}.data"
STORAGE_VERSION: Final = 1
STORAGE_MINOR_VERSION: Final = 2

# --- Config / options keys -------------------------------------------------
CONF_DEFAULT_NOTIFY: Final = "default_notify_service"   # e.g. "notify.mobile_app_pixel"
CONF_TTS_ENGINE: Final = "tts_engine"                   # e.g. "tts.home_assistant_cloud"
CONF_TTS_MEDIA_PLAYER: Final = "tts_media_player"       # e.g. "media_player.kitchen"
CONF_QUIET_START: Final = "quiet_hours_start"           # "HH:MM"
CONF_QUIET_END: Final = "quiet_hours_end"               # "HH:MM"
CONF_NAG_INTERVAL: Final = "default_nag_interval_min"   # int minutes
CONF_SNOOZE_CAP: Final = "snooze_cap"                   # int, max consecutive snoozes

# --- Defaults --------------------------------------------------------------
DEFAULT_NAG_INTERVAL_MIN: Final = 30
DEFAULT_SNOOZE_CAP: Final = 3
DEFAULT_QUIET_START: Final = "22:00"
DEFAULT_QUIET_END: Final = "07:00"

# How often the nag engine wakes up to evaluate due/overdue tasks.
NAG_TICK_SECONDS: Final = 60

# --- Actionable notification action ids ------------------------------------
ACTION_COMPLETE: Final = f"{DOMAIN}_complete"
ACTION_SNOOZE: Final = f"{DOMAIN}_snooze"
ACTION_PUSH_NEXT: Final = f"{DOMAIN}_push_next"

# Event fired internally when a mobile action comes back.
EVENT_MOBILE_ACTION: Final = "mobile_app_notification_action"


class Frequency(StrEnum):
    """Repeat frequency for a task."""

    NONE = "none"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class NotificationType(StrEnum):
    """How a task's reminders/nags are delivered."""

    NONE = "none"
    PUSH = "push"            # mobile_app actionable notification
    ANNOUNCE = "announce"    # TTS on a media_player
    BOTH = "both"


class TaskStatus(StrEnum):
    """Lifecycle state of a task (mirrors HA TodoItemStatus where relevant)."""

    NEEDS_ACTION = "needs_action"
    COMPLETED = "completed"


# --- Service names ---------------------------------------------------------
SERVICE_CREATE_TASK: Final = "create_task"
SERVICE_EDIT_TASK: Final = "edit_task"
SERVICE_DELETE_TASK: Final = "delete_task"
SERVICE_COMPLETE_TASK: Final = "complete_task"
SERVICE_SNOOZE_TASK: Final = "snooze_task"
SERVICE_PUSH_NEXT: Final = "push_to_next"
SERVICE_ADD_SUBTASK: Final = "add_subtask"
SERVICE_TOGGLE_SUBTASK: Final = "toggle_subtask"
SERVICE_CREATE_CATEGORY: Final = "create_category"
SERVICE_EDIT_CATEGORY: Final = "edit_category"
SERVICE_DELETE_CATEGORY: Final = "delete_category"

# Dispatcher signal used to tell entities/card the store changed.
SIGNAL_STORE_UPDATED: Final = f"{DOMAIN}_store_updated"
