from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.camera.webrtc import (
    RTCIceCandidateInit,
    WebRTCAnswer,
    WebRTCSendMessage,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    MQTT_TOPIC_AVAILABILITY,
    MQTT_TOPIC_CAMERA_STATUS,
    SIGNAL_NEW_CAMERAS,
)
from .coordinator import VedettaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VedettaCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[str] = {c["name"] for c in coordinator.cameras}
    async_add_entities(
        VedettaCamera(entry, coordinator, camera) for camera in coordinator.cameras
    )

    @callback
    def _add_new_cameras(new_cameras: list[dict]) -> None:
        fresh = [c for c in new_cameras if c["name"] not in known]
        if not fresh:
            return
        known.update(c["name"] for c in fresh)
        async_add_entities(VedettaCamera(entry, coordinator, c) for c in fresh)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_NEW_CAMERAS.format(entry_id=entry.entry_id),
            _add_new_cameras,
        )
    )


class VedettaCamera(Camera):
    """Live camera entity for a Vedetta NVR camera.

    Supports WebRTC for low-latency live streaming, with MJPEG as a fallback.
    On-demand snapshots are fetched directly from the Vedetta API.

    Availability is driven by two MQTT topics:
      * NVR-level availability  ({prefix}/availability — "online"/"offline")
      * Per-camera status       ({prefix}/camera/{name}/status — "ON"/"OFF")
    A camera is reported available only when BOTH report a positive value.
    The entity starts unavailable so HA shows the correct state until MQTT
    catches up after a restart.
    """

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_has_entity_name = True
    _attr_name = None  # use device name as entity name

    def __init__(self, entry: ConfigEntry, coordinator: VedettaCoordinator, camera: dict) -> None:
        super().__init__()
        self._coordinator = coordinator
        self._camera_name: str = camera["name"]
        self._active_sessions: set[str] = set()
        self._nvr_online: bool = False
        self._camera_on: bool = False
        self._attr_available = False
        self._attr_unique_id = f"{entry.entry_id}_{self._camera_name}_camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self._camera_name}")},
            name=f"Vedetta {self._camera_name}",
            manufacturer="Vedetta",
        )

    @property
    def available(self) -> bool:
        return self._nvr_online and self._camera_on

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT availability topics for this camera."""
        prefix = self._coordinator.mqtt_prefix
        availability_topic = MQTT_TOPIC_AVAILABILITY.format(prefix=prefix)
        status_topic = MQTT_TOPIC_CAMERA_STATUS.format(
            prefix=prefix, camera=self._camera_name
        )

        unsub_avail = await mqtt.async_subscribe(
            self.hass, availability_topic, self._handle_nvr_availability
        )
        unsub_status = await mqtt.async_subscribe(
            self.hass, status_topic, self._handle_camera_status
        )
        self.async_on_remove(unsub_avail)
        self.async_on_remove(unsub_status)

    @callback
    def _handle_nvr_availability(self, msg: mqtt.ReceiveMessage) -> None:
        self._nvr_online = msg.payload == "online"
        self.async_write_ha_state()

    @callback
    def _handle_camera_status(self, msg: mqtt.ReceiveMessage) -> None:
        self._camera_on = msg.payload == "ON"
        self.async_write_ha_state()

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
        the send_message callback. Duplicate calls for the same session_id are
        silently ignored — the first answer already sent remains valid.
        """
        if session_id in self._active_sessions:
            return
        self._active_sessions.add(session_id)
        try:
            response = await self._coordinator.api.webrtc_offer(
                self._camera_name, offer_sdp
            )
            send_message(WebRTCAnswer(answer=response["sdp"]))
        except Exception:
            self._active_sessions.discard(session_id)
            raise

    def close_webrtc_session(self, session_id: str) -> None:
        """Remove a closed WebRTC session so the camera can be re-opened."""
        self._active_sessions.discard(session_id)

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Absorb trickled ICE candidates from the browser.

        Vedetta's NVR uses non-trickle ICE: the SDP answer returned by
        `POST /api/cameras/{name}/webrtc/offer` already contains every server
        candidate inline, and there is no candidate endpoint to forward to.
        We must still accept the WebSocket messages HA generates, otherwise
        the base class raises `HomeAssistantError("Cannot handle WebRTC
        candidate")` and the negotiation aborts before media starts flowing.
        """
        return None
