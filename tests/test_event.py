import json
from unittest.mock import MagicMock, patch

from custom_components.vedetta.event import VedettaDetectionEvent


def _make_entity(camera_name: str = "front-door") -> VedettaDetectionEvent:
    coordinator = MagicMock()
    coordinator.mqtt_prefix = "vedetta"
    coordinator.cameras = [{"name": camera_name}]

    entity = VedettaDetectionEvent.__new__(VedettaDetectionEvent)
    entity._coordinator = coordinator
    entity._camera_name = camera_name
    entity._attr_unique_id = f"vedetta_{camera_name}_detection_event"
    entity._attr_name = f"{camera_name} Detection"
    return entity


def test_detection_start_event() -> None:
    entity = _make_entity()
    entity._trigger_event = MagicMock()
    entity.async_write_ha_state = MagicMock()

    payload = json.dumps(
        {
            "event_id": "evt-001",
            "label": "person",
            "score": 0.92,
            "box": [10, 20, 100, 200],
            "zone_name": "driveway",
            "object_name": "person_1",
            "sub_label": None,
        }
    )
    entity._handle_event(MagicMock(payload=payload))

    entity._trigger_event.assert_called_once()
    call_args = entity._trigger_event.call_args
    event_type, event_data = call_args[0]

    assert event_type == "detection_start"
    assert event_data["event_id"] == "evt-001"
    assert event_data["label"] == "person"
    assert event_data["score"] == 0.92
    assert event_data["box"] == [10, 20, 100, 200]
    assert event_data["zone_name"] == "driveway"
    assert event_data["object_name"] == "person_1"
    assert "end_time" not in event_data
    entity.async_write_ha_state.assert_called_once()


def test_detection_end_event() -> None:
    entity = _make_entity()
    entity._trigger_event = MagicMock()
    entity.async_write_ha_state = MagicMock()

    payload = json.dumps(
        {
            "event_id": "evt-002",
            "label": "car",
            "score": 0.85,
            "box": [5, 10, 80, 160],
            "zone_name": "street",
            "object_name": "car_1",
            "sub_label": "sedan",
            "end_time": "2026-04-08T12:34:56Z",
        }
    )
    entity._handle_event(MagicMock(payload=payload))

    entity._trigger_event.assert_called_once()
    call_args = entity._trigger_event.call_args
    event_type, event_data = call_args[0]

    assert event_type == "detection_end"
    assert event_data["event_id"] == "evt-002"
    assert event_data["label"] == "car"
    assert event_data["sub_label"] == "sedan"
    assert event_data["end_time"] == "2026-04-08T12:34:56Z"
    entity.async_write_ha_state.assert_called_once()
