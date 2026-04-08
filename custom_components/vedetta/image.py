from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components import mqtt
from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import VedettaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VedettaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        VedettaDetectionImage(hass, entry, coordinator, camera)
        for camera in coordinator.cameras
    )


class VedettaDetectionImage(ImageEntity):
    """Last detection snapshot for a Vedetta camera, updated via MQTT."""

    _attr_has_entity_name = True
    _attr_name = "Last Detection"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: VedettaCoordinator,
        camera: dict,
    ) -> None:
        super().__init__(hass)
        self._coordinator = coordinator
        self._camera = camera
        self._camera_name: str = camera["name"]
        self._image_data: bytes | None = None
        self._attr_unique_id = f"{entry.entry_id}_{self._camera_name}_detection_image"
        self._attr_extra_state_attributes: dict = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self._camera_name}")},
            name=self._camera_name,
            manufacturer="Vedetta",
        )

    async def async_added_to_hass(self) -> None:
        topic = f"{self._coordinator.mqtt_prefix}/{self._camera_name}/+/snapshot"
        unsub = await mqtt.async_subscribe(self.hass, topic, self._handle_snapshot)
        self.async_on_remove(unsub)

    @callback
    def _handle_snapshot(self, msg: mqtt.ReceiveMessage) -> None:
        """Store incoming JPEG bytes and extract the detection label from the topic."""
        self._image_data = msg.payload
        parts = msg.topic.split("/")
        label = parts[-2] if len(parts) >= 2 else "unknown"
        self._attr_extra_state_attributes = {"label": label}
        self._attr_image_last_updated = datetime.now(timezone.utc)
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        return self._image_data
