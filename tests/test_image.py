from datetime import timezone
from unittest.mock import MagicMock, patch

from custom_components.vedetta.image import VedettaDetectionImage


ENTRY_ID = "test_entry_id"


def _make_entity(camera_name: str = "front-door", mqtt_prefix: str = "vedetta") -> VedettaDetectionImage:
    """Construct a VedettaDetectionImage without HA infrastructure."""
    coordinator = MagicMock()
    coordinator.mqtt_prefix = mqtt_prefix
    camera = {"name": camera_name}

    entity = VedettaDetectionImage.__new__(VedettaDetectionImage)
    entity._coordinator = coordinator
    entity._camera = camera
    entity._camera_name = camera_name
    entity._image_data = None
    entity._attr_unique_id = f"{ENTRY_ID}_{camera_name}_detection_image"
    entity._attr_extra_state_attributes = {}
    entity._attr_image_last_updated = None
    entity.async_write_ha_state = MagicMock()
    return entity


def _make_mqtt_msg(topic: str, payload: bytes) -> MagicMock:
    msg = MagicMock()
    msg.topic = topic
    msg.payload = payload
    return msg


def test_snapshot_received() -> None:
    """MQTT snapshot payload is stored and timestamp is updated."""
    entity = _make_entity()
    jpeg = b"\xff\xd8\xff\xe0test_image_data"
    msg = _make_mqtt_msg("vedetta/front-door/person/snapshot", jpeg)

    entity._handle_snapshot(msg)

    assert entity._image_data == jpeg
    assert entity._attr_image_last_updated is not None
    assert entity._attr_image_last_updated.tzinfo == timezone.utc
    entity.async_write_ha_state.assert_called_once()


def test_snapshot_extracts_label_from_topic() -> None:
    """Detection label is extracted from the second-to-last topic segment."""
    entity = _make_entity()
    jpeg = b"\xff\xd8\xff\xe0car_snapshot"
    msg = _make_mqtt_msg("vedetta/backyard/car/snapshot", jpeg)

    entity._handle_snapshot(msg)

    assert entity._attr_extra_state_attributes["label"] == "car"


def test_snapshot_updates_label_on_subsequent_messages() -> None:
    """Label attribute reflects the most recent MQTT message."""
    entity = _make_entity()

    entity._handle_snapshot(_make_mqtt_msg("vedetta/front-door/person/snapshot", b"img1"))
    assert entity._attr_extra_state_attributes["label"] == "person"

    entity._handle_snapshot(_make_mqtt_msg("vedetta/front-door/car/snapshot", b"img2"))
    assert entity._attr_extra_state_attributes["label"] == "car"
    assert entity._image_data == b"img2"


async def test_async_image_returns_stored_bytes() -> None:
    """async_image() returns whatever bytes were last stored."""
    entity = _make_entity()
    jpeg = b"\xff\xd8\xff\xe0some_bytes"
    entity._image_data = jpeg

    result = await entity.async_image()

    assert result == jpeg


async def test_async_image_returns_none_when_no_snapshot_received() -> None:
    """async_image() returns None before any snapshot is received."""
    entity = _make_entity()

    result = await entity.async_image()

    assert result is None
