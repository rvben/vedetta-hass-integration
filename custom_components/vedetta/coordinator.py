import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VedettaApiClient
from .const import SIGNAL_NEW_CAMERAS

_LOGGER = logging.getLogger(__name__)

HEALTH_SCAN_INTERVAL = timedelta(seconds=60)


class VedettaCoordinator:
    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        token: str,
        mqtt_prefix: str,
        entry_id: str | None = None,
    ) -> None:
        self.hass = hass
        self.mqtt_prefix = mqtt_prefix
        self.entry_id = entry_id
        self.api = VedettaApiClient(
            host=host,
            token=token,
            session=async_get_clientsession(hass),
        )
        self.cameras: list[dict] = []
        self.health_coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="vedetta_health",
            update_method=self._async_fetch_health,
            update_interval=HEALTH_SCAN_INTERVAL,
        )

    async def async_setup(self) -> None:
        self.cameras = await self.api.get_cameras()
        await self.health_coordinator.async_config_entry_first_refresh()

    async def _async_fetch_health(self) -> dict:
        """Fetch health + camera roster, dispatching newly-discovered cameras.

        Camera-list fetch failures are tolerated so transient API hiccups do
        not knock the whole integration unhealthy; only the health call's
        outcome propagates as UpdateFailed.
        """
        await self._refresh_camera_roster()
        try:
            return await self.api.get_health()
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch health: {err}") from err

    async def _refresh_camera_roster(self) -> None:
        try:
            cameras = await self.api.get_cameras()
        except Exception as err:
            _LOGGER.debug("camera list refresh failed: %s", err)
            return

        known = {c["name"] for c in self.cameras}
        new_cameras = [c for c in cameras if c["name"] not in known]
        self.cameras = cameras

        if new_cameras and self.entry_id is not None:
            async_dispatcher_send(
                self.hass,
                SIGNAL_NEW_CAMERAS.format(entry_id=self.entry_id),
                new_cameras,
            )

    def get_camera(self, name: str) -> dict | None:
        for cam in self.cameras:
            if cam["name"] == name:
                return cam
        return None
