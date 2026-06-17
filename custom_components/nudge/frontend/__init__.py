"""Frontend (Lovelace card) registration for Nudge.

Serves the card's JavaScript over a static HTTP path and auto-registers it as a
Lovelace resource (in storage mode), so the user doesn't have to add the
resource by hand. Follows the Home Assistant "embedded card in an integration"
pattern. Registration must run once, after HA has started, from async_setup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

_DIR = Path(__file__).parent
_MANIFEST = _DIR.parent / "manifest.json"

# Public URL the card JS is served from, e.g. /nudge/nudge-card.js
URL_BASE = "/nudge"
JSMODULES: list[dict[str, str]] = [{"name": "Nudge Card", "filename": "nudge-card.js"}]


def _version() -> str:
    """Read the integration version from manifest.json (for cache-busting)."""
    try:
        return json.loads(_MANIFEST.read_text(encoding="utf-8")).get("version", "0.0.0")
    except Exception:  # noqa: BLE001
        return "0.0.0"


class JSModuleRegistration:
    """Registers the card's static path and Lovelace resource."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.lovelace = hass.data.get("lovelace")

    async def async_register(self) -> None:
        await self._async_register_static_path()
        if self._mode() == "storage":
            await self._async_wait_for_resources()

    def _mode(self) -> str:
        lc = self.lovelace
        return getattr(lc, "mode", None) or getattr(lc, "resource_mode", "yaml")

    async def _async_register_static_path(self) -> None:
        try:
            await self.hass.http.async_register_static_paths(
                [StaticPathConfig(URL_BASE, str(_DIR), False)]
            )
            _LOGGER.debug("Nudge: static path %s -> %s", URL_BASE, _DIR)
        except RuntimeError:
            # Already registered (e.g. integration reloaded) — fine.
            _LOGGER.debug("Nudge: static path %s already registered", URL_BASE)

    async def _async_wait_for_resources(self) -> None:
        resources = getattr(self.lovelace, "resources", None)
        if resources is None:
            _LOGGER.debug("Nudge: no Lovelace resources collection; skipping auto-register")
            return

        async def _check(_now: Any = None) -> None:
            if not resources.loaded:
                async_call_later(self.hass, 5, _check)
                return
            await self._async_register_modules(resources)

        await _check()

    async def _async_register_modules(self, resources) -> None:
        version = _version()
        existing = [
            r for r in resources.async_items() if str(r.get("url", "")).startswith(URL_BASE)
        ]
        for module in JSMODULES:
            url = f"{URL_BASE}/{module['filename']}"
            versioned = f"{url}?v={version}"
            match = next((r for r in existing if r["url"].split("?")[0] == url), None)
            if match is None:
                await resources.async_create_item({"res_type": "module", "url": versioned})
                _LOGGER.info("Nudge: registered Lovelace resource %s", versioned)
            elif match["url"] != versioned:
                await resources.async_update_item(
                    match["id"], {"res_type": "module", "url": versioned}
                )
                _LOGGER.info("Nudge: updated Lovelace resource to %s", versioned)


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Entry point called from async_setup (after HA has started)."""
    await JSModuleRegistration(hass).async_register()
