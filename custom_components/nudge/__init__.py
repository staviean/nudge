"""The Nudge integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .store import NudgeStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TODO]

type NudgeConfigEntry = ConfigEntry["NudgeRuntimeData"]


class NudgeRuntimeData:
    """Runtime objects shared across the integration."""

    def __init__(self, store: NudgeStore) -> None:
        self.store = store
        # nag_engine is attached in a later chunk.
        self.nag_engine = None


async def async_setup_entry(hass: HomeAssistant, entry: NudgeConfigEntry) -> bool:
    """Set up Nudge from a config entry."""
    store = NudgeStore(hass)
    await store.async_load()

    entry.runtime_data = NudgeRuntimeData(store)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entities/services when options change.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("Nudge set up successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NudgeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: NudgeConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
