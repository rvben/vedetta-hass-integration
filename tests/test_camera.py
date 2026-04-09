from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.vedetta.camera import VedettaCamera
from custom_components.vedetta.coordinator import VedettaCoordinator

ENTRY_ID = "test_entry_id"


def make_entry(entry_id: str = ENTRY_ID) -> MagicMock:
    entry = MagicMock()
    entry.entry_id = entry_id
    return entry


def make_camera(camera_name: str = "front-door", ptz: bool = False) -> VedettaCamera:
    """Construct a VedettaCamera without a live HA instance."""
    entry = make_entry()
    coordinator = MagicMock(spec=VedettaCoordinator)
    coordinator.api = AsyncMock()
    camera_dict = {"name": camera_name, "ptz": ptz}
    return VedettaCamera(entry, coordinator, camera_dict)


async def test_camera_unique_id() -> None:
    """Each camera gets a stable unique ID namespaced by entry_id."""
    cam = make_camera("backyard")
    assert cam.unique_id == f"{ENTRY_ID}_backyard_camera"


async def test_camera_unique_id_front_door() -> None:
    """Unique ID contains the entry_id prefix and camera name verbatim."""
    cam = make_camera("front-door")
    assert cam.unique_id == f"{ENTRY_ID}_front-door_camera"


async def test_camera_image() -> None:
    """async_camera_image returns the bytes from the API get_snapshot call."""
    image_data = b"\xff\xd8\xff\xe0snapshot"
    cam = make_camera("front-door")
    cam._coordinator.api.get_snapshot = AsyncMock(return_value=image_data)

    result = await cam.async_camera_image()

    assert result == image_data
    cam._coordinator.api.get_snapshot.assert_called_once_with("front-door")


async def test_camera_image_width_height_ignored() -> None:
    """Width/height parameters are accepted but not forwarded to the API."""
    image_data = b"\xff\xd8\xff"
    cam = make_camera("garden")
    cam._coordinator.api.get_snapshot = AsyncMock(return_value=image_data)

    result = await cam.async_camera_image(width=640, height=480)

    assert result == image_data
    cam._coordinator.api.get_snapshot.assert_called_once_with("garden")


async def test_webrtc_offer() -> None:
    """WebRTC offer is proxied to the API and the SDP answer is sent back."""
    sdp_offer = "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n"
    sdp_answer = "v=0\r\no=- 1 1 IN IP4 192.168.1.180\r\n"

    cam = make_camera("front-door")
    cam._coordinator.api.webrtc_offer = AsyncMock(
        return_value={"type": "answer", "sdp": sdp_answer}
    )

    sent_messages: list = []
    cam._coordinator.api.webrtc_offer  # ensure it exists

    await cam.async_handle_async_webrtc_offer(
        offer_sdp=sdp_offer,
        session_id="session-abc",
        send_message=sent_messages.append,
    )

    cam._coordinator.api.webrtc_offer.assert_called_once_with("front-door", sdp_offer)
    assert len(sent_messages) == 1
    answer = sent_messages[0]
    assert answer.answer == sdp_answer


async def test_webrtc_offer_different_camera() -> None:
    """WebRTC offer uses the entity's own camera name."""
    cam = make_camera("backyard")
    cam._coordinator.api.webrtc_offer = AsyncMock(
        return_value={"type": "answer", "sdp": "sdp-answer"}
    )

    await cam.async_handle_async_webrtc_offer(
        offer_sdp="sdp-offer",
        session_id="session-xyz",
        send_message=lambda _: None,
    )

    cam._coordinator.api.webrtc_offer.assert_called_once_with("backyard", "sdp-offer")


async def test_webrtc_offer_duplicate_session_ignored() -> None:
    """A duplicate offer for an in-flight session is silently dropped."""
    cam = make_camera("front-door")
    cam._coordinator.api.webrtc_offer = AsyncMock(
        return_value={"type": "answer", "sdp": "sdp-answer"}
    )

    sent_messages: list = []

    await cam.async_handle_async_webrtc_offer(
        offer_sdp="offer",
        session_id="dup-session",
        send_message=sent_messages.append,
    )
    # Second call with the same session_id must not produce another answer.
    await cam.async_handle_async_webrtc_offer(
        offer_sdp="offer",
        session_id="dup-session",
        send_message=sent_messages.append,
    )

    assert len(sent_messages) == 1
    cam._coordinator.api.webrtc_offer.assert_called_once()


async def test_webrtc_close_session_allows_reopen() -> None:
    """Closing a session removes it so a new offer for the same id is accepted."""
    cam = make_camera("front-door")
    cam._coordinator.api.webrtc_offer = AsyncMock(
        return_value={"type": "answer", "sdp": "sdp-answer"}
    )

    sent_messages: list = []

    await cam.async_handle_async_webrtc_offer(
        offer_sdp="offer",
        session_id="session-reopen",
        send_message=sent_messages.append,
    )
    cam.close_webrtc_session("session-reopen")

    await cam.async_handle_async_webrtc_offer(
        offer_sdp="offer",
        session_id="session-reopen",
        send_message=sent_messages.append,
    )

    assert len(sent_messages) == 2
    assert cam._coordinator.api.webrtc_offer.call_count == 2


async def test_webrtc_offer_error_removes_session() -> None:
    """A failed API call removes the session so the offer can be retried."""
    cam = make_camera("front-door")
    cam._coordinator.api.webrtc_offer = AsyncMock(side_effect=RuntimeError("timeout"))

    sent_messages: list = []

    with pytest.raises(RuntimeError):
        await cam.async_handle_async_webrtc_offer(
            offer_sdp="offer",
            session_id="session-fail",
            send_message=sent_messages.append,
        )

    # Session must not remain active after the error.
    assert "session-fail" not in cam._active_sessions

    # A subsequent offer for the same session_id must be forwarded.
    cam._coordinator.api.webrtc_offer = AsyncMock(
        return_value={"type": "answer", "sdp": "sdp-answer"}
    )
    await cam.async_handle_async_webrtc_offer(
        offer_sdp="offer",
        session_id="session-fail",
        send_message=sent_messages.append,
    )
    assert len(sent_messages) == 1


async def test_camera_device_name_prefixed() -> None:
    """DeviceInfo name is prefixed with 'Vedetta ' to avoid collision with NVR auto-discovery."""
    cam = make_camera("front-door")
    assert cam.device_info["name"] == "Vedetta front-door"


async def test_camera_device_name_prefixed_backyard() -> None:
    cam = make_camera("backyard")
    assert cam.device_info["name"] == "Vedetta backyard"
