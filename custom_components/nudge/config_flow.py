"""Config flow for the Nudge integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
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
    DOMAIN,
)


class NudgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup. Single instance."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Nudge", data={}, options=user_input)

        schema = vol.Schema(
            {
                vol.Optional(CONF_DEFAULT_NOTIFY): str,
                vol.Optional(CONF_TTS_ENGINE, default="tts.home_assistant_cloud"): str,
                vol.Optional(CONF_TTS_MEDIA_PLAYER): str,
                vol.Optional(CONF_QUIET_START, default=DEFAULT_QUIET_START): str,
                vol.Optional(CONF_QUIET_END, default=DEFAULT_QUIET_END): str,
                vol.Optional(
                    CONF_NAG_INTERVAL, default=DEFAULT_NAG_INTERVAL_MIN
                ): vol.All(int, vol.Range(min=1, max=1440)),
                vol.Optional(CONF_SNOOZE_CAP, default=DEFAULT_SNOOZE_CAP): vol.All(
                    int, vol.Range(min=0, max=20)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NudgeOptionsFlow()


class NudgeOptionsFlow(OptionsFlow):
    """Allow editing notification targets, quiet hours, and nag defaults."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DEFAULT_NOTIFY,
                    default=opts.get(CONF_DEFAULT_NOTIFY, ""),
                ): str,
                vol.Optional(
                    CONF_TTS_ENGINE,
                    default=opts.get(CONF_TTS_ENGINE, "tts.home_assistant_cloud"),
                ): str,
                vol.Optional(
                    CONF_TTS_MEDIA_PLAYER,
                    default=opts.get(CONF_TTS_MEDIA_PLAYER, ""),
                ): str,
                vol.Optional(
                    CONF_QUIET_START,
                    default=opts.get(CONF_QUIET_START, DEFAULT_QUIET_START),
                ): str,
                vol.Optional(
                    CONF_QUIET_END,
                    default=opts.get(CONF_QUIET_END, DEFAULT_QUIET_END),
                ): str,
                vol.Optional(
                    CONF_NAG_INTERVAL,
                    default=opts.get(CONF_NAG_INTERVAL, DEFAULT_NAG_INTERVAL_MIN),
                ): vol.All(int, vol.Range(min=1, max=1440)),
                vol.Optional(
                    CONF_SNOOZE_CAP,
                    default=opts.get(CONF_SNOOZE_CAP, DEFAULT_SNOOZE_CAP),
                ): vol.All(int, vol.Range(min=0, max=20)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
