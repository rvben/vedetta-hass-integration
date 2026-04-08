from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VedettaApiClient


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

    async def async_setup(self) -> None:
        self.cameras = await self.api.get_cameras()

    def get_camera(self, name: str) -> dict | None:
        for cam in self.cameras:
            if cam["name"] == name:
                return cam
        return None
