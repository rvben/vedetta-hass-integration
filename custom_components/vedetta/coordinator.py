import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VedettaApiClient

_LOGGER = logging.getLogger(__name__)

HEALTH_SCAN_INTERVAL = timedelta(seconds=60)


class VedettaCoordinator:
    def __init__(self, hass: HomeAssistant, host: str, token: str, mqtt_prefix: str) -> None:
        self.hass = hass
        self.mqtt_prefix = mqtt_prefix
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
        try:
            return await self.api.get_health()
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch health: {err}") from err

    def get_camera(self, name: str) -> dict | None:
        for cam in self.cameras:
            if cam["name"] == name:
                return cam
        return None
