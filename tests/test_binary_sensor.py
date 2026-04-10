"""Tests for binary sensor message handling.

Sensors are tested in isolation by constructing them via __new__, wiring up
required attributes, and invoking _handle_message directly — no full HA
platform setup required.
"""

from unittest.mock import MagicMock

import pytest

from custom_components.vedetta.binary_sensor import (
    VedettaAvailabilitySensor,
    VedettaCameraStatusSensor,
    VedettaDetectionSensor,
    VedettaObjectCountSensor,
    VedettaOperationalSensor,
    VedettaZonePresenceSensor,
)


def _make_msg(payload: str, topic: str = "") -> MagicMock:
    msg = MagicMock()
    msg.payload = payload
    msg.topic = topic
    return msg


def _availability_sensor() -> VedettaAvailabilitySensor:
    sensor = VedettaAvailabilitySensor.__new__(VedettaAvailabilitySensor)
    sensor._attr_is_on = False
    sensor.async_write_ha_state = MagicMock()
    return sensor


def _camera_status_sensor() -> VedettaCameraStatusSensor:
    sensor = VedettaCameraStatusSensor.__new__(VedettaCameraStatusSensor)
    sensor._attr_is_on = False
    sensor.async_write_ha_state = MagicMock()
    return sensor


def _object_count_sensor() -> VedettaObjectCountSensor:
    sensor = VedettaObjectCountSensor.__new__(VedettaObjectCountSensor)
    sensor._attr_is_on = False
    sensor._count = 0
    sensor._camera_name = "front_door"
    sensor._label = "person"
    sensor.async_write_ha_state = MagicMock()
    return sensor


def _zone_presence_sensor() -> VedettaZonePresenceSensor:
    sensor = VedettaZonePresenceSensor.__new__(VedettaZonePresenceSensor)
    sensor._attr_is_on = False
    sensor.async_write_ha_state = MagicMock()
    return sensor


# ---------------------------------------------------------------------------
# VedettaAvailabilitySensor
# ---------------------------------------------------------------------------


def test_availability_online() -> None:
    sensor = _availability_sensor()
    sensor._handle_message(_make_msg("online"))
    assert sensor._attr_is_on is True
    sensor.async_write_ha_state.assert_called_once()


def test_availability_offline() -> None:
    sensor = _availability_sensor()
    sensor._attr_is_on = True
    sensor._handle_message(_make_msg("offline"))
    assert sensor._attr_is_on is False
    sensor.async_write_ha_state.assert_called_once()


def test_availability_unknown_payload_is_off() -> None:
    sensor = _availability_sensor()
    sensor._attr_is_on = True
    sensor._handle_message(_make_msg("connecting"))
    assert sensor._attr_is_on is False


# ---------------------------------------------------------------------------
# VedettaCameraStatusSensor
# ---------------------------------------------------------------------------


def test_camera_status_on() -> None:
    sensor = _camera_status_sensor()
    sensor._handle_message(_make_msg("ON"))
    assert sensor._attr_is_on is True
    sensor.async_write_ha_state.assert_called_once()


def test_camera_status_off() -> None:
    sensor = _camera_status_sensor()
    sensor._attr_is_on = True
    sensor._handle_message(_make_msg("OFF"))
    assert sensor._attr_is_on is False
    sensor.async_write_ha_state.assert_called_once()


def test_camera_status_unknown_payload_is_off() -> None:
    sensor = _camera_status_sensor()
    sensor._attr_is_on = True
    sensor._handle_message(_make_msg("STANDBY"))
    assert sensor._attr_is_on is False


# ---------------------------------------------------------------------------
# VedettaObjectCountSensor
# ---------------------------------------------------------------------------


def test_object_count_on() -> None:
    sensor = _object_count_sensor()
    sensor._handle_message(_make_msg("3"))
    assert sensor._attr_is_on is True
    assert sensor._count == 3
    sensor.async_write_ha_state.assert_called_once()


def test_object_count_off() -> None:
    sensor = _object_count_sensor()
    sensor._attr_is_on = True
    sensor._count = 2
    sensor._handle_message(_make_msg("0"))
    assert sensor._attr_is_on is False
    assert sensor._count == 0
    sensor.async_write_ha_state.assert_called_once()


def test_object_count_in_extra_attributes() -> None:
    sensor = _object_count_sensor()
    sensor._handle_message(_make_msg("5"))
    assert sensor.extra_state_attributes == {"count": 5}


def test_object_count_invalid_payload_no_state_change() -> None:
    """An unparseable payload must not update state or write HA state."""
    sensor = _object_count_sensor()
    sensor._attr_is_on = True
    sensor._count = 2
    sensor._handle_message(_make_msg("not-a-number"))
    # State and count must remain unchanged
    assert sensor._attr_is_on is True
    assert sensor._count == 2
    sensor.async_write_ha_state.assert_not_called()


# ---------------------------------------------------------------------------
# VedettaZonePresenceSensor
# ---------------------------------------------------------------------------


def test_zone_presence_entered() -> None:
    sensor = _zone_presence_sensor()
    sensor._handle_message(_make_msg("entered"))
    assert sensor._attr_is_on is True
    sensor.async_write_ha_state.assert_called_once()


def test_zone_presence_left() -> None:
    sensor = _zone_presence_sensor()
    sensor._attr_is_on = True
    sensor._handle_message(_make_msg("left"))
    assert sensor._attr_is_on is False
    sensor.async_write_ha_state.assert_called_once()


def test_zone_presence_unknown_payload_is_off() -> None:
    sensor = _zone_presence_sensor()
    sensor._attr_is_on = True
    sensor._handle_message(_make_msg("idle"))
    assert sensor._attr_is_on is False


# ---------------------------------------------------------------------------
# Entity naming (has_entity_name = True — no camera prefix in _attr_name)
# ---------------------------------------------------------------------------


def test_camera_status_sensor_name_is_terse() -> None:
    """With has_entity_name=True the name must not include the camera prefix."""
    entry = MagicMock()
    entry.entry_id = "eid"
    sensor = VedettaCameraStatusSensor(entry, "vedetta", "garage")
    assert sensor._attr_name == "Status"
    assert "garage" not in sensor._attr_name


def test_object_count_sensor_name_contains_label_only() -> None:
    """Object count name includes the label but not the camera name."""
    entry = MagicMock()
    entry.entry_id = "eid"
    sensor = VedettaObjectCountSensor(entry, "vedetta", "front_door", "person")
    assert sensor._attr_name == "person Count"
    assert "front_door" not in sensor._attr_name


def test_zone_presence_sensor_name_has_no_zone_prefix() -> None:
    """Zone presence name is '{zone} {label}' (no 'Zone' prefix) under NVR device."""
    entry = MagicMock()
    entry.entry_id = "eid"
    sensor = VedettaZonePresenceSensor(entry, "vedetta", "driveway", "car")
    assert sensor._attr_name == "driveway car"
    assert sensor._attr_name.startswith("Zone") is False


# ---------------------------------------------------------------------------
# Helpers for coordinator-based sensors
# ---------------------------------------------------------------------------

_HEALTH_OK = {
    "status": "ok",
    "uptime": "38s",
    "version": "75ce3c5",
    "checks": {
        "cameras": {"online": 5, "total": 5},
        "database": "ok",
        "mqtt": "connected",
        "detection": {
            "state": "ok",
            "openh264_loaded": True,
            "openh264_version": "2.6.0",
        },
        "storage": {
            "used": "342.5 GB",
            "disk_low": False,
        },
    },
}

_HEALTH_DEGRADED = {
    "status": "degraded",
    "uptime": "120s",
    "version": "75ce3c5",
    "checks": {
        "cameras": {"online": 4, "total": 5},
        "detection": {
            "state": "disabled",
            "openh264_loaded": False,
            "reason": "OpenH264 codec not loaded: missing library",
        },
    },
}


def _mock_health_coordinator(data: dict) -> MagicMock:
    """Return a minimal mock that looks like a DataUpdateCoordinator to sensors."""
    coord = MagicMock()
    coord.data = data
    # async_add_listener is called by CoordinatorEntity.__init__ via super().__init__
    coord.async_add_listener = MagicMock(return_value=lambda: None)
    return coord


def _operational_sensor(health_data: dict) -> VedettaOperationalSensor:
    entry = MagicMock()
    entry.entry_id = "eid"
    coordinator = MagicMock()
    coordinator.health_coordinator = _mock_health_coordinator(health_data)
    sensor = VedettaOperationalSensor.__new__(VedettaOperationalSensor)
    # Wire the CoordinatorEntity internals manually (bypassing __init__ super chain)
    sensor.coordinator = coordinator.health_coordinator
    sensor._attr_unique_id = f"{entry.entry_id}_operational"
    sensor._attr_device_info = MagicMock()
    return sensor


def _detection_sensor(health_data: dict) -> VedettaDetectionSensor:
    entry = MagicMock()
    entry.entry_id = "eid"
    coordinator = MagicMock()
    coordinator.health_coordinator = _mock_health_coordinator(health_data)
    sensor = VedettaDetectionSensor.__new__(VedettaDetectionSensor)
    sensor.coordinator = coordinator.health_coordinator
    sensor._attr_unique_id = f"{entry.entry_id}_detection"
    sensor._attr_device_info = MagicMock()
    return sensor


# ---------------------------------------------------------------------------
# VedettaOperationalSensor
# ---------------------------------------------------------------------------


def test_operational_sensor_off_when_status_ok() -> None:
    sensor = _operational_sensor(_HEALTH_OK)
    assert sensor.is_on is False


def test_operational_sensor_on_when_status_degraded() -> None:
    sensor = _operational_sensor(_HEALTH_DEGRADED)
    assert sensor.is_on is True


def test_operational_sensor_on_when_status_missing() -> None:
    """Missing status key defaults to 'ok', so sensor is OFF (no problem detected)."""
    sensor = _operational_sensor({})
    assert sensor.is_on is False


def test_operational_sensor_attributes_contain_checks() -> None:
    sensor = _operational_sensor(_HEALTH_OK)
    attrs = sensor.extra_state_attributes
    assert "cameras" in attrs
    assert "detection" in attrs
    assert "database" in attrs


def test_operational_sensor_attributes_empty_on_no_data() -> None:
    sensor = _operational_sensor({})
    assert sensor.extra_state_attributes == {}


def test_operational_sensor_device_class_is_problem() -> None:
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    sensor = _operational_sensor(_HEALTH_OK)
    assert sensor.device_class == BinarySensorDeviceClass.PROBLEM


def test_operational_sensor_name() -> None:
    sensor = _operational_sensor(_HEALTH_OK)
    assert sensor.name == "Operational"


def test_operational_sensor_unique_id() -> None:
    entry = MagicMock()
    entry.entry_id = "test-entry-id"
    coordinator = MagicMock()
    coordinator.health_coordinator = _mock_health_coordinator(_HEALTH_OK)
    sensor = VedettaOperationalSensor.__new__(VedettaOperationalSensor)
    sensor.coordinator = coordinator.health_coordinator
    sensor._attr_unique_id = f"{entry.entry_id}_operational"
    sensor._attr_device_info = MagicMock()
    assert sensor._attr_unique_id == "test-entry-id_operational"


# ---------------------------------------------------------------------------
# VedettaDetectionSensor
# ---------------------------------------------------------------------------


def test_detection_sensor_on_when_state_ok() -> None:
    sensor = _detection_sensor(_HEALTH_OK)
    assert sensor.is_on is True


def test_detection_sensor_off_when_state_disabled() -> None:
    sensor = _detection_sensor(_HEALTH_DEGRADED)
    assert sensor.is_on is False


def test_detection_sensor_off_when_no_data() -> None:
    sensor = _detection_sensor({})
    assert sensor.is_on is False


def test_detection_sensor_attributes_include_openh264_loaded() -> None:
    sensor = _detection_sensor(_HEALTH_OK)
    attrs = sensor.extra_state_attributes
    assert attrs["openh264_loaded"] is True
    assert attrs["openh264_version"] == "2.6.0"
    assert "reason" not in attrs


def test_detection_sensor_attributes_include_reason_when_disabled() -> None:
    sensor = _detection_sensor(_HEALTH_DEGRADED)
    attrs = sensor.extra_state_attributes
    assert attrs["openh264_loaded"] is False
    assert attrs["reason"] == "OpenH264 codec not loaded: missing library"
    assert "openh264_version" not in attrs


def test_detection_sensor_attributes_empty_on_no_data() -> None:
    sensor = _detection_sensor({})
    attrs = sensor.extra_state_attributes
    assert attrs["openh264_loaded"] is None


def test_detection_sensor_device_class_is_running() -> None:
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    sensor = _detection_sensor(_HEALTH_OK)
    assert sensor.device_class == BinarySensorDeviceClass.RUNNING


def test_detection_sensor_name() -> None:
    sensor = _detection_sensor(_HEALTH_OK)
    assert sensor.name == "Detection"


def test_detection_sensor_unique_id() -> None:
    entry = MagicMock()
    entry.entry_id = "test-entry-id"
    coordinator = MagicMock()
    coordinator.health_coordinator = _mock_health_coordinator(_HEALTH_OK)
    sensor = VedettaDetectionSensor.__new__(VedettaDetectionSensor)
    sensor.coordinator = coordinator.health_coordinator
    sensor._attr_unique_id = f"{entry.entry_id}_detection"
    sensor._attr_device_info = MagicMock()
    assert sensor._attr_unique_id == "test-entry-id_detection"
