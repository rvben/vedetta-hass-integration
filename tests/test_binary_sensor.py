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
    VedettaObjectCountSensor,
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
