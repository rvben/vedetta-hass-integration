from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import VedettaCoordinator

PTZ_DIRECTIONS = ["up", "down", "left", "right", "zoom_in", "zoom_out"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VedettaCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        VedettaPTZButton(coordinator, cam["name"], direction)
        for cam in coordinator.cameras
        if cam.get("ptz")
        for direction in PTZ_DIRECTIONS
    ]
    async_add_entities(entities)


class VedettaPTZButton(ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: VedettaCoordinator,
        camera_name: str,
        direction: str,
    ) -> None:
        self._coordinator = coordinator
        self._camera_name = camera_name
        self._direction = direction
        self._attr_unique_id = f"{camera_name}_ptz_{direction}"
        self._attr_name = f"{camera_name} PTZ {direction.replace('_', ' ').title()}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera_name)},
            name=camera_name,
            manufacturer="Vedetta",
        )

    async def async_press(self) -> None:
        await self._coordinator.api.send_ptz(self._camera_name, self._direction)
