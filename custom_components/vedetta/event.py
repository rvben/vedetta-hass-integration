from __future__ import annotations

import json
import logging

from homeassistant.components import mqtt
from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MQTT_TOPIC_EVENTS
from .coordinator import VedettaCoordinator

_LOGGER = logging.getLogger(__name__)

EVENT_TYPES = ["detection_start", "detection_end"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VedettaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        VedettaDetectionEvent(hass, entry, coordinator, camera["name"])
        for camera in coordinator.cameras
    ]
    async_add_entities(entities)


class VedettaDetectionEvent(EventEntity):
    _attr_has_entity_name = True
    _attr_event_types = EVENT_TYPES

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: VedettaCoordinator,
        camera_name: str,
    ) -> None:
        self.hass = hass
        self._coordinator = coordinator
        self._camera_name = camera_name
        self._attr_unique_id = f"{entry.entry_id}_{camera_name}_detection_event"
        self._attr_name = f"{camera_name} Detection"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{camera_name}")},
            name=camera_name,
            manufacturer="Vedetta",
        )

    async def async_added_to_hass(self) -> None:
        topic = MQTT_TOPIC_EVENTS.format(
            prefix=self._coordinator.mqtt_prefix,
            camera=self._camera_name,
        )
        unsub = await mqtt.async_subscribe(self.hass, topic, self._handle_event)
        self.async_on_remove(unsub)

    @callback
    def _handle_event(self, msg) -> None:
        try:
            data = json.loads(msg.payload)
        except (json.JSONDecodeError, ValueError):
            _LOGGER.warning(
                "Vedetta: invalid JSON on event topic for camera %s: %s",
                self._camera_name,
                msg.payload,
            )
            return

        event_data: dict = {
            "event_id": data.get("event_id"),
            "label": data.get("label"),
            "score": data.get("score"),
            "box": data.get("box"),
            "zone_name": data.get("zone_name"),
            "object_name": data.get("object_name"),
            "sub_label": data.get("sub_label"),
        }

        if "end_time" in data:
            event_data["end_time"] = data["end_time"]
            event_type = "detection_end"
        else:
            event_type = "detection_start"

        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()
