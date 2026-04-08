from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX, DOMAIN
from .coordinator import VedettaCoordinator

PLATFORMS = ["binary_sensor", "camera", "image", "event", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = VedettaCoordinator(
        hass=hass,
        host=entry.data["host"],
        token=entry.data["api_token"],
        mqtt_prefix=entry.data.get(CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX),
    )
    await coordinator.async_setup()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
