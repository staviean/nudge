"""The Nudge integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .nag_engine import NagEngine
from .services import async_register_services, async_unregister_services
from .store import NudgeStore
from .websocket import async_register_ws

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TODO]

type NudgeConfigEntry = ConfigEntry["NudgeRuntimeData"]


class NudgeRuntimeData:
    """Runtime objects shared across the integration."""

    def __init__(self, store: NudgeStore, nag_engine: NagEngine) -> None:
        self.store = store
        self.nag_engine = nag_engine


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-wide pieces (websocket API) once at startup."""
    async_register_ws(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NudgeConfigEntry) -> bool:
    """Set up Nudge from a config entry."""
    store = NudgeStore(hass)
    await store.async_load()

    # Expose the store to the websocket API so the card has a read path.
    hass.data.setdefault(DOMAIN, {})["store"] = store

    nag_engine = NagEngine(hass, store, entry)
    await nag_engine.async_start()

    entry.runtime_data = NudgeRuntimeData(store, nag_engine)

    # Register all nudge.* services.
    async_register_services(hass, store)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entities/services when options change.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("Nudge set up successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NudgeConfigEntry) -> bool:
    """Unload a config entry."""
    runtime: NudgeRuntimeData | None = getattr(entry, "runtime_data", None)
    if runtime is not None and runtime.nag_engine is not None:
        await runtime.nag_engine.async_stop()
    # Remove services so the next async_setup_entry re-registers them
    # with a fresh store reference (avoids stale-handler bug on reload).
    async_unregister_services(hass)
    hass.data.get(DOMAIN, {}).pop("store", None)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: NudgeConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
