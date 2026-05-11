"""Tests for VedettaCoordinator camera-list refresh and discovery dispatch.

The coordinator's health poll doubles as a camera-list poll: each refresh
fetches the camera roster, updates `self.cameras`, and emits a dispatcher
signal carrying any newly-discovered cameras so platforms can register new
entities without an HA restart.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.vedetta import coordinator as coordinator_module
from custom_components.vedetta.const import SIGNAL_NEW_CAMERAS
from custom_components.vedetta.coordinator import VedettaCoordinator

ENTRY_ID = "entry-coord"


def _make_coordinator(initial_cameras: list[dict]) -> VedettaCoordinator:
    """Build a VedettaCoordinator without invoking the real __init__.

    The HA DataUpdateCoordinator base requires a fully-set-up hass instance,
    which is overkill for verifying the small fetch/dispatch logic we own.
    """
    coord = VedettaCoordinator.__new__(VedettaCoordinator)
    coord.hass = MagicMock()
    coord.mqtt_prefix = "vedetta"
    coord.entry_id = ENTRY_ID
    coord.api = AsyncMock()
    coord.cameras = list(initial_cameras)
    coord.health_coordinator = MagicMock()
    return coord


async def test_coordinator_accepts_entry_id() -> None:
    """entry_id is accepted as a constructor argument so dispatcher signals can be scoped per-entry."""
    import inspect

    sig = inspect.signature(VedettaCoordinator.__init__)
    assert "entry_id" in sig.parameters


async def test_refresh_updates_cameras_list() -> None:
    """Each refresh replaces self.cameras with the latest API response."""
    coord = _make_coordinator([{"name": "front"}])
    coord.api.get_health = AsyncMock(return_value={"status": "ok"})
    coord.api.get_cameras = AsyncMock(
        return_value=[{"name": "front"}, {"name": "back"}]
    )

    with patch.object(coordinator_module, "async_dispatcher_send") as send:
        await coord._async_fetch_health()

    assert [c["name"] for c in coord.cameras] == ["front", "back"]
    send.assert_called_once()


async def test_refresh_dispatches_new_cameras_only() -> None:
    """The dispatcher payload contains only cameras absent from the previous snapshot."""
    coord = _make_coordinator([{"name": "front"}])
    coord.api.get_health = AsyncMock(return_value={"status": "ok"})
    coord.api.get_cameras = AsyncMock(
        return_value=[{"name": "front"}, {"name": "back"}, {"name": "garage"}]
    )

    with patch.object(coordinator_module, "async_dispatcher_send") as send:
        await coord._async_fetch_health()

    signal_name, payload = send.call_args.args[1], send.call_args.args[2]
    assert signal_name == SIGNAL_NEW_CAMERAS.format(entry_id=ENTRY_ID)
    assert {c["name"] for c in payload} == {"back", "garage"}


async def test_refresh_does_not_dispatch_when_no_new_cameras() -> None:
    """Stable polls do not emit a dispatcher signal — listeners only see real adds."""
    coord = _make_coordinator([{"name": "front"}, {"name": "back"}])
    coord.api.get_health = AsyncMock(return_value={"status": "ok"})
    coord.api.get_cameras = AsyncMock(
        return_value=[{"name": "front"}, {"name": "back"}]
    )

    with patch.object(coordinator_module, "async_dispatcher_send") as send:
        await coord._async_fetch_health()

    send.assert_not_called()


async def test_refresh_does_not_dispatch_when_camera_removed() -> None:
    """A shrinking roster is not a discovery event."""
    coord = _make_coordinator([{"name": "front"}, {"name": "back"}])
    coord.api.get_health = AsyncMock(return_value={"status": "ok"})
    coord.api.get_cameras = AsyncMock(return_value=[{"name": "front"}])

    with patch.object(coordinator_module, "async_dispatcher_send") as send:
        await coord._async_fetch_health()

    send.assert_not_called()
    assert [c["name"] for c in coord.cameras] == ["front"]


async def test_refresh_returns_health_payload() -> None:
    """The DataUpdateCoordinator hook must still return the health dict."""
    coord = _make_coordinator([])
    health = {"status": "ok", "uptime": "10s"}
    coord.api.get_health = AsyncMock(return_value=health)
    coord.api.get_cameras = AsyncMock(return_value=[])

    with patch.object(coordinator_module, "async_dispatcher_send"):
        result = await coord._async_fetch_health()

    assert result == health


async def test_refresh_propagates_health_failure_as_update_failed() -> None:
    """A failing health call surfaces as UpdateFailed so HA marks the entry unhealthy."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    coord = _make_coordinator([])
    coord.api.get_health = AsyncMock(side_effect=RuntimeError("boom"))
    coord.api.get_cameras = AsyncMock(return_value=[])

    with patch.object(coordinator_module, "async_dispatcher_send"):
        with pytest.raises(UpdateFailed):
            await coord._async_fetch_health()


async def test_refresh_continues_when_camera_list_call_fails() -> None:
    """A flaky camera-list call must not break health polling — degrade gracefully."""
    coord = _make_coordinator([{"name": "front"}])
    coord.api.get_health = AsyncMock(return_value={"status": "ok"})
    coord.api.get_cameras = AsyncMock(side_effect=RuntimeError("nope"))

    with patch.object(coordinator_module, "async_dispatcher_send") as send:
        result = await coord._async_fetch_health()

    assert result == {"status": "ok"}
    send.assert_not_called()
    # Previous roster preserved so the UI doesn't blink to "no cameras".
    assert [c["name"] for c in coord.cameras] == ["front"]
