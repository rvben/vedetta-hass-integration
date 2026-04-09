from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.vedetta.api import VedettaApiClient, VedettaApiError


async def test_get_cameras(api_client: VedettaApiClient) -> None:
    cameras = [
        {"id": "front-door", "name": "Front Door"},
        {"id": "backyard", "name": "Backyard"},
    ]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=cameras)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.get = MagicMock(return_value=mock_response)

    result = await api_client.get_cameras()

    assert result == cameras
    api_client._session.get.assert_called_once_with(
        "http://192.168.1.180:5050/api/cameras",
        headers={"Authorization": "Bearer test-token"},
    )


async def test_check_health(api_client: VedettaApiClient) -> None:
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.get = MagicMock(return_value=mock_response)

    result = await api_client.check_health()

    assert result is True
    api_client._session.get.assert_called_once_with(
        "http://192.168.1.180:5050/api/health",
        headers={"Authorization": "Bearer test-token"},
    )


async def test_check_health_failure(api_client: VedettaApiClient) -> None:
    mock_response = AsyncMock()
    mock_response.status = 503
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.get = MagicMock(return_value=mock_response)

    result = await api_client.check_health()

    assert result is False


async def test_get_snapshot(api_client: VedettaApiClient) -> None:
    image_data = b"\xff\xd8\xff\xe0snapshot_data"
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.read = AsyncMock(return_value=image_data)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.get = MagicMock(return_value=mock_response)

    result = await api_client.get_snapshot("front-door")

    assert result == image_data
    api_client._session.get.assert_called_once_with(
        "http://192.168.1.180:5050/api/cameras/front-door/snapshot",
        headers={"Authorization": "Bearer test-token"},
    )


async def test_send_ptz_move_command(api_client: VedettaApiClient) -> None:
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.post = MagicMock(return_value=mock_response)

    await api_client.send_ptz("garage", "left")

    api_client._session.post.assert_called_once_with(
        "http://192.168.1.180:5050/api/cameras/garage/ptz",
        headers={"Authorization": "Bearer test-token"},
        json={"action": "move", "direction": "left"},
    )


async def test_send_ptz_zoom_in_command(api_client: VedettaApiClient) -> None:
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.post = MagicMock(return_value=mock_response)

    await api_client.send_ptz("garage", "zoom_in")

    api_client._session.post.assert_called_once_with(
        "http://192.168.1.180:5050/api/cameras/garage/ptz",
        headers={"Authorization": "Bearer test-token"},
        json={"action": "zoom", "direction": "in"},
    )


async def test_send_ptz_zoom_out_command(api_client: VedettaApiClient) -> None:
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.post = MagicMock(return_value=mock_response)

    await api_client.send_ptz("garage", "zoom_out")

    api_client._session.post.assert_called_once_with(
        "http://192.168.1.180:5050/api/cameras/garage/ptz",
        headers={"Authorization": "Bearer test-token"},
        json={"action": "zoom", "direction": "out"},
    )


async def test_get_events(api_client: VedettaApiClient) -> None:
    events = [
        {"id": "evt-001", "camera": "front-door", "label": "person"},
        {"id": "evt-002", "camera": "backyard", "label": "car"},
    ]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=events)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.get = MagicMock(return_value=mock_response)

    result = await api_client.get_events(camera="front-door", limit=10)

    assert result == events
    api_client._session.get.assert_called_once_with(
        "http://192.168.1.180:5050/api/events",
        headers={"Authorization": "Bearer test-token"},
        params={"limit": "10", "camera": "front-door"},
    )


async def test_get_events_no_camera_filter(api_client: VedettaApiClient) -> None:
    events = [{"id": "evt-001", "camera": "front-door", "label": "person"}]
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=events)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.get = MagicMock(return_value=mock_response)

    result = await api_client.get_events()

    assert result == events
    api_client._session.get.assert_called_once_with(
        "http://192.168.1.180:5050/api/events",
        headers={"Authorization": "Bearer test-token"},
        params={"limit": "50"},
    )


async def test_webrtc_offer(api_client: VedettaApiClient) -> None:
    sdp_answer = {"type": "answer", "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n..."}
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=sdp_answer)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.post = MagicMock(return_value=mock_response)

    result = await api_client.webrtc_offer("front-door", "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n...")

    assert result == sdp_answer
    api_client._session.post.assert_called_once_with(
        "http://192.168.1.180:5050/api/cameras/front-door/webrtc/offer",
        headers={"Authorization": "Bearer test-token"},
        json={"type": "offer", "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n..."},
    )


async def test_get_cameras_error(api_client: VedettaApiClient) -> None:
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.get = MagicMock(return_value=mock_response)

    with pytest.raises(VedettaApiError, match="Failed to get cameras: 500"):
        await api_client.get_cameras()


async def test_send_ptz_command_error(api_client: VedettaApiClient) -> None:
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)
    api_client._session.post = MagicMock(return_value=mock_response)

    with pytest.raises(VedettaApiError, match="PTZ command failed: 404"):
        await api_client.send_ptz("nonexistent", "left")
