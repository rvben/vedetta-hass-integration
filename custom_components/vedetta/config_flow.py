import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VedettaApiClient
from .const import CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("api_token"): str,
        vol.Optional(CONF_MQTT_PREFIX, default=DEFAULT_MQTT_PREFIX): str,
    }
)


class VedettaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = VedettaApiClient(
                host=user_input["host"],
                token=user_input["api_token"],
                session=session,
            )

            try:
                healthy = await client.check_health()
            except Exception:
                healthy = False

            if healthy:
                await self.async_set_unique_id(user_input["host"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Vedetta", data=user_input)

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
