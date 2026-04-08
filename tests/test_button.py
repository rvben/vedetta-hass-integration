from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.vedetta.button import VedettaPTZButton


def make_coordinator(cameras: list[dict]) -> MagicMock:
    coordinator = MagicMock()
    coordinator.cameras = cameras
    coordinator.api = MagicMock()
    coordinator.api.send_ptz = AsyncMock()
    return coordinator


async def test_ptz_press() -> None:
    coordinator = make_coordinator([{"name": "front-door", "ptz": True}])
    button = object.__new__(VedettaPTZButton)
    button._coordinator = coordinator
    button._camera_name = "front-door"
    button._direction = "left"

    await button.async_press()

    coordinator.api.send_ptz.assert_called_once_with("front-door", "left")


async def test_ptz_press_zoom() -> None:
    coordinator = make_coordinator([{"name": "patio", "ptz": True}])
    button = object.__new__(VedettaPTZButton)
    button._coordinator = coordinator
    button._camera_name = "patio"
    button._direction = "zoom_in"

    await button.async_press()

    coordinator.api.send_ptz.assert_called_once_with("patio", "zoom_in")


async def test_ptz_buttons_only_for_ptz_cameras() -> None:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    cameras = [
        {"name": "front-door", "ptz": True},
        {"name": "backyard", "ptz": False},
        {"name": "garage", "ptz": True},
    ]
    coordinator = make_coordinator(cameras)

    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    hass.data = {"vedetta": {"test_entry": coordinator}}

    added: list = []
    async_add_entities = MagicMock(side_effect=lambda entities: added.extend(entities))

    from custom_components.vedetta.button import async_setup_entry, PTZ_DIRECTIONS

    await async_setup_entry(hass, entry, async_add_entities)

    # Only PTZ-capable cameras get buttons (front-door and garage, not backyard)
    expected_count = 2 * len(PTZ_DIRECTIONS)
    assert len(added) == expected_count
    camera_names = {btn._camera_name for btn in added}
    assert "front-door" in camera_names
    assert "garage" in camera_names
    assert "backyard" not in camera_names
