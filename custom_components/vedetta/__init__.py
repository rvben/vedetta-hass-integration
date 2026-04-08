from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

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

    async def handle_snapshot(call: ServiceCall) -> ServiceResponse:
        entity_id: str = call.data["entity_id"]
        entity_registry = er.async_get(hass)
        entity_entry = entity_registry.async_get(entity_id)
        if entity_entry is None:
            raise ServiceValidationError(f"Entity {entity_id} not found")
        # Unique ID format: "{entry_id}_{camera_name}_camera"
        unique_id = entity_entry.unique_id or ""
        camera_name = unique_id.removeprefix(f"{entry.entry_id}_").removesuffix("_camera")
        if not camera_name or camera_name == unique_id:
            raise ServiceValidationError(f"Cannot determine camera name from {entity_id}")
        snapshot_data = await coordinator.api.get_snapshot(camera_name)
        snapshot_dir = Path(hass.config.path("www", "vedetta"))
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = snapshot_dir / f"{camera_name}_latest.jpg"
        await hass.async_add_executor_job(path.write_bytes, snapshot_data)
        return {"path": f"/local/vedetta/{camera_name}_latest.jpg"}

    hass.services.async_register(
        DOMAIN,
        "snapshot",
        handle_snapshot,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Remove the snapshot service when no entries remain
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "snapshot")
    return unload_ok
