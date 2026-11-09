"""Set up, reauthenticate and reconfigure a connection to Immich."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import ImmichAuthError, ImmichClient, ImmichConnectionError, ImmichError
from .const import DOMAIN, REQUIRED_PERMISSIONS, STATISTICS_PERMISSIONS

try:
    import probatio as vol
except ImportError:  # Home Assistant before 2026.9
    import voluptuous as vol  # type: ignore[no-redef]

KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
URL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))

SERVER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): URL_SELECTOR,
        vol.Required(CONF_API_KEY): KEY_SELECTOR,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)
KEY_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): KEY_SELECTOR})
PERMISSIONS = ", ".join(REQUIRED_PERMISSIONS)
STATISTICS = ", ".join(STATISTICS_PERMISSIONS)


def normalize_url(url: str) -> str | None:
    """Return the server's address without a trailing slash or /api, or None if it isn't one."""
    url = url.strip().rstrip("/")
    if url.endswith("/api"):
        url = url[: -len("/api")]
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    return url


class ImmichSlideshowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the server address and an API key."""

    VERSION = 1

    async def _check(self, url: str, api_key: str, verify_ssl: bool) -> dict[str, str]:
        client = ImmichClient(async_get_clientsession(self.hass, verify_ssl), url, api_key)
        try:
            missing = await client.async_missing_permissions()
        except ImmichAuthError:
            return {"base": "invalid_auth"}
        except ImmichConnectionError:
            return {"base": "cannot_connect"}
        except ImmichError:
            return {"base": "unknown"}
        if missing:
            self._missing = ", ".join(missing)
            return {"base": "missing_permissions"}
        return {}

    def _placeholders(self) -> dict[str, str]:
        return {"permissions": PERMISSIONS, "statistics": STATISTICS, "missing": getattr(self, "_missing", "")}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add a server."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            if url is None:
                errors[CONF_URL] = "invalid_url"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                errors = await self._check(url, user_input[CONF_API_KEY], user_input[CONF_VERIFY_SSL])
                if not errors:
                    return self.async_create_entry(
                        title=urlsplit(url).hostname or url,
                        data={**user_input, CONF_URL: url},
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                SERVER_SCHEMA, {k: v for k, v in (user_input or {}).items() if k != CONF_API_KEY}
            ),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Immich refused the key, or it lost a permission."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._check(
                entry.data[CONF_URL], user_input[CONF_API_KEY], entry.data.get(CONF_VERIFY_SSL, True)
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=KEY_SCHEMA,
            errors=errors,
            description_placeholders={**self._placeholders(), "url": entry.data[CONF_URL]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address or the key."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            if url is None:
                errors[CONF_URL] = "invalid_url"
            else:
                await self.async_set_unique_id(url)
                if url != entry.unique_id:
                    self._abort_if_unique_id_configured()
                errors = await self._check(url, user_input[CONF_API_KEY], user_input[CONF_VERIFY_SSL])
                if not errors:
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=url,
                        title=urlsplit(url).hostname or url,
                        data={**user_input, CONF_URL: url},
                    )
        suggested = {
            CONF_URL: entry.data[CONF_URL],
            CONF_VERIFY_SSL: entry.data.get(CONF_VERIFY_SSL, True),
            **{k: v for k, v in (user_input or {}).items() if k != CONF_API_KEY},
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(SERVER_SCHEMA, suggested),
            errors=errors,
            description_placeholders=self._placeholders(),
        )
