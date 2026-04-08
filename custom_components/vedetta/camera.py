from __future__ import annotations

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.camera.webrtc import WebRTCAnswer, WebRTCSendMessage
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import VedettaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VedettaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        VedettaCamera(entry, coordinator, camera) for camera in coordinator.cameras
    )


class VedettaCamera(Camera):
    """Live camera entity for a Vedetta NVR camera.

    Supports WebRTC for low-latency live streaming, with MJPEG as a fallback.
    On-demand snapshots are fetched directly from the Vedetta API.
    """

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_has_entity_name = True
    _attr_name = None  # use device name as entity name

    def __init__(self, entry: ConfigEntry, coordinator: VedettaCoordinator, camera: dict) -> None:
        super().__init__()
        self._coordinator = coordinator
        self._camera_name: str = camera["name"]
        self._attr_unique_id = f"{entry.entry_id}_{self._camera_name}_camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self._camera_name}")},
            name=self._camera_name,
            manufacturer="Vedetta",
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a snapshot image from the camera."""
        return await self._coordinator.api.get_snapshot(self._camera_name)

    async def async_handle_async_webrtc_offer(
        self,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
    ) -> None:
        """Handle a WebRTC offer by proxying it to the Vedetta API.

        The API returns an SDP answer which is forwarded to the frontend via
        the send_message callback.
        """
        response = await self._coordinator.api.webrtc_offer(
            self._camera_name, offer_sdp
        )
        send_message(WebRTCAnswer(answer=response["sdp"]))
