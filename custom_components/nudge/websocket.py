"""WebSocket API for the Nudge frontend card.

The custom card is a read-only projection of the Nudge store; all writes still
go through the ``nudge.*`` services. These commands give the card a fast,
live-updating read path:

* ``nudge/get_data``  -> one-shot snapshot of categories + tasks
* ``nudge/subscribe`` -> initial snapshot, then a fresh snapshot on every
                         store change (driven by SIGNAL_STORE_UPDATED)
* ``nudge/version``   -> integration version, used by the card for cache-busting
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_STORE_UPDATED

_MANIFEST = Path(__file__).parent / "manifest.json"


def _version() -> str:
    """Read the integration version from manifest.json (best effort)."""
    try:
        return json.loads(_MANIFEST.read_text(encoding="utf-8")).get("version", "0.0.0")
    except Exception:  # noqa: BLE001
        return "0.0.0"


def _get_store(hass: HomeAssistant):
    """Return the live NudgeStore, or None if the entry isn't set up yet."""
    return (hass.data.get(DOMAIN) or {}).get("store")


def _payload(store) -> dict[str, Any]:
    """Serialize the full store for the card."""
    return {
        "categories": [c.to_dict() for c in store.categories.values()],
        "tasks": [t.to_dict() for t in store.tasks.values()],
    }


@callback
def async_register_ws(hass: HomeAssistant) -> None:
    """Register all Nudge websocket commands (called once from async_setup)."""
    websocket_api.async_register_command(hass, ws_get_data)
    websocket_api.async_register_command(hass, ws_version)
    websocket_api.async_register_command(hass, ws_subscribe)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_data"})
@callback
def ws_get_data(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return a one-shot snapshot of categories + tasks."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_ready", "Nudge store is not loaded")
        return
    connection.send_result(msg["id"], _payload(store))


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/version"})
@callback
def ws_version(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return the integration version for frontend cache-busting."""
    connection.send_result(msg["id"], {"version": _version()})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Subscribe to live store updates.

    Sends an initial snapshot immediately, then a fresh snapshot whenever the
    store dispatches SIGNAL_STORE_UPDATED. The subscription is torn down
    automatically when the client unsubscribes or disconnects.
    """

    @callback
    def _forward() -> None:
        store = _get_store(hass)
        if store is not None:
            connection.send_message(
                websocket_api.event_message(msg["id"], _payload(store))
            )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, SIGNAL_STORE_UPDATED, _forward
    )
    connection.send_result(msg["id"])
    _forward()  # push an initial snapshot so the card renders immediately
