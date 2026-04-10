from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MQTT_TOPIC_AVAILABILITY,
    MQTT_TOPIC_CAMERA_STATUS,
    MQTT_TOPIC_OBJECT_COUNT,
    MQTT_TOPIC_PRESENCE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    prefix = coordinator.mqtt_prefix

    entities: list[BinarySensorEntity] = []

    # NVR-level health sensors (polled via HTTP)
    entities.append(VedettaOperationalSensor(entry, coordinator))
    entities.append(VedettaDetectionSensor(entry, coordinator))

    # One availability sensor for the whole Vedetta system
    entities.append(VedettaAvailabilitySensor(entry, prefix))

    # One camera status sensor per known camera
    for camera in coordinator.cameras:
        entities.append(VedettaCameraStatusSensor(entry, prefix, camera["name"]))

    async_add_entities(entities)

    # Dynamic discovery: object count and zone presence sensors are created on
    # first matching MQTT message and added via async_add_entities.
    discovered_object_count: set[tuple[str, str]] = set()
    discovered_zone_presence: set[tuple[str, str, str]] = set()

    @callback
    def _handle_object_count_discovery(msg: mqtt.ReceiveMessage) -> None:
        """Discover object count sensors from wildcard subscription."""
        # Topic pattern: {prefix}/{camera}/{label}
        # Skip snapshot sub-topics: {prefix}/{camera}/{label}/snapshot
        topic = msg.topic
        remainder = topic[len(prefix) + 1:]  # strip "prefix/"
        parts = remainder.split("/")

        # Exactly two parts: camera and label (no snapshot suffix)
        if len(parts) != 2:
            return

        camera_name, label = parts
        # Skip known sub-topic prefixes that aren't object counts
        if camera_name in ("events", "camera", "presence", "objects"):
            return

        key = (camera_name, label)
        if key in discovered_object_count:
            return

        discovered_object_count.add(key)
        sensor = VedettaObjectCountSensor(entry, prefix, camera_name, label)
        async_add_entities([sensor])
        # Replay the triggering message so the sensor has an initial state
        sensor._handle_message(msg)

    @callback
    def _handle_zone_presence_discovery(msg: mqtt.ReceiveMessage) -> None:
        """Discover zone presence sensors from wildcard subscription."""
        # Topic pattern: {prefix}/presence/{zone}/{label}
        topic = msg.topic
        remainder = topic[len(prefix) + 1:]  # strip "prefix/"
        parts = remainder.split("/")

        # Must be: presence / {zone} / {label}
        if len(parts) != 3 or parts[0] != "presence":
            return

        _, zone, label = parts
        key = (entry.entry_id, zone, label)
        if key in discovered_zone_presence:
            return

        discovered_zone_presence.add(key)
        sensor = VedettaZonePresenceSensor(entry, prefix, zone, label)
        async_add_entities([sensor])
        sensor._handle_message(msg)

    # Subscribe to wildcard topics for dynamic discovery.
    # Object counts: {prefix}/+/+  (two-level wildcard catches camera/label)
    # Zone presence: {prefix}/presence/+/+
    unsub_object_count = await mqtt.async_subscribe(
        hass,
        f"{prefix}/+/+",
        _handle_object_count_discovery,
    )
    unsub_zone_presence = await mqtt.async_subscribe(
        hass,
        f"{prefix}/presence/+/+",
        _handle_zone_presence_discovery,
    )
    entry.async_on_unload(unsub_object_count)
    entry.async_on_unload(unsub_zone_presence)


def _camera_device(entry: ConfigEntry, camera_name: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{camera_name}")},
        name=f"Vedetta {camera_name}",
        manufacturer="Vedetta",
    )


class VedettaAvailabilitySensor(BinarySensorEntity):
    """Binary sensor that is ON when the Vedetta NVR reports 'online'."""

    _attr_has_entity_name = True
    _attr_name = "Availability"

    def __init__(self, entry: ConfigEntry, prefix: str) -> None:
        self._entry = entry
        self._prefix = prefix
        self._attr_unique_id = f"{entry.entry_id}_availability"
        self._attr_is_on = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Vedetta NVR",
            manufacturer="Vedetta",
        )

    async def async_added_to_hass(self) -> None:
        topic = MQTT_TOPIC_AVAILABILITY.format(prefix=self._prefix)
        unsub = await mqtt.async_subscribe(self.hass, topic, self._handle_message)
        self.async_on_remove(unsub)

    @callback
    def _handle_message(self, msg: mqtt.ReceiveMessage) -> None:
        self._attr_is_on = msg.payload == "online"
        self.async_write_ha_state()


class VedettaCameraStatusSensor(BinarySensorEntity):
    """Binary sensor that is ON when the camera reports status 'ON'."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, prefix: str, camera_name: str) -> None:
        self._entry = entry
        self._prefix = prefix
        self._camera_name = camera_name
        self._attr_unique_id = f"{entry.entry_id}_{camera_name}_status"
        self._attr_name = "Status"
        self._attr_is_on = False
        self._attr_device_info = _camera_device(entry, camera_name)

    async def async_added_to_hass(self) -> None:
        topic = MQTT_TOPIC_CAMERA_STATUS.format(
            prefix=self._prefix, camera=self._camera_name
        )
        unsub = await mqtt.async_subscribe(self.hass, topic, self._handle_message)
        self.async_on_remove(unsub)

    @callback
    def _handle_message(self, msg: mqtt.ReceiveMessage) -> None:
        self._attr_is_on = msg.payload == "ON"
        self.async_write_ha_state()


class VedettaObjectCountSensor(BinarySensorEntity):
    """Binary sensor ON when at least one object of a given label is detected.

    The current count is exposed as an extra state attribute.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        prefix: str,
        camera_name: str,
        label: str,
    ) -> None:
        self._entry = entry
        self._prefix = prefix
        self._camera_name = camera_name
        self._label = label
        self._count = 0
        self._attr_unique_id = f"{entry.entry_id}_{camera_name}_{label}_count"
        self._attr_name = f"{label} Count"
        self._attr_is_on = False
        self._attr_device_info = _camera_device(entry, camera_name)

    async def async_added_to_hass(self) -> None:
        topic = MQTT_TOPIC_OBJECT_COUNT.format(
            prefix=self._prefix, camera=self._camera_name, label=self._label
        )
        unsub = await mqtt.async_subscribe(self.hass, topic, self._handle_message)
        self.async_on_remove(unsub)

    @callback
    def _handle_message(self, msg: mqtt.ReceiveMessage) -> None:
        try:
            self._count = int(msg.payload)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Unexpected payload for object count sensor %s/%s: %r",
                self._camera_name,
                self._label,
                msg.payload,
            )
            return
        self._attr_is_on = self._count > 0
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"count": self._count}


class VedettaZonePresenceSensor(BinarySensorEntity):
    """Binary sensor ON while a label is present in a zone (state == 'entered')."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        prefix: str,
        zone: str,
        label: str,
    ) -> None:
        self._entry = entry
        self._prefix = prefix
        self._zone = zone
        self._label = label
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}_{label}"
        self._attr_name = f"{zone} {label}"
        self._attr_is_on = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Vedetta NVR",
            manufacturer="Vedetta",
        )

    async def async_added_to_hass(self) -> None:
        topic = MQTT_TOPIC_PRESENCE.format(
            prefix=self._prefix, zone=self._zone, label=self._label
        )
        unsub = await mqtt.async_subscribe(self.hass, topic, self._handle_message)
        self.async_on_remove(unsub)

    @callback
    def _handle_message(self, msg: mqtt.ReceiveMessage) -> None:
        self._attr_is_on = msg.payload == "entered"
        self.async_write_ha_state()


def _nvr_device(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Vedetta NVR",
        manufacturer="Vedetta",
    )


class VedettaOperationalSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor that is ON (problem) when any Vedetta subsystem is degraded.

    Polls the /api/health endpoint via DataUpdateCoordinator. Device class PROBLEM
    means ON = something is wrong, OFF = all systems healthy.
    """

    _attr_has_entity_name = True
    _attr_name = "Operational"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        super().__init__(coordinator.health_coordinator)
        self._attr_unique_id = f"{entry.entry_id}_operational"
        self._attr_device_info = _nvr_device(entry)

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        return data.get("status", "ok") != "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("checks", {})


class VedettaDetectionSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor that is ON when the Vedetta detection pipeline is running.

    Polls the /api/health endpoint via DataUpdateCoordinator. Device class RUNNING
    means ON = detection pipeline is active, OFF = detection is disabled or broken.
    """

    _attr_has_entity_name = True
    _attr_name = "Detection"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        super().__init__(coordinator.health_coordinator)
        self._attr_unique_id = f"{entry.entry_id}_detection"
        self._attr_device_info = _nvr_device(entry)

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        detection = data.get("checks", {}).get("detection", {})
        return detection.get("state", "") == "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        detection = data.get("checks", {}).get("detection", {})
        attrs: dict[str, Any] = {
            "openh264_loaded": detection.get("openh264_loaded"),
        }
        if "openh264_version" in detection:
            attrs["openh264_version"] = detection["openh264_version"]
        if "reason" in detection:
            attrs["reason"] = detection["reason"]
        return attrs
