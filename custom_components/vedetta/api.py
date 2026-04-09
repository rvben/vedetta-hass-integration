from aiohttp import ClientSession


class VedettaApiError(Exception):
    pass


class VedettaApiClient:
    def __init__(self, host: str, token: str, session: ClientSession) -> None:
        self._host = host.rstrip("/")
        self._token = token
        self._session = session

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def check_health(self) -> bool:
        async with self._session.get(
            f"{self._host}/api/health", headers=self._headers
        ) as resp:
            return resp.status == 200

    async def get_cameras(self) -> list[dict]:
        async with self._session.get(
            f"{self._host}/api/cameras", headers=self._headers
        ) as resp:
            if resp.status != 200:
                raise VedettaApiError(f"Failed to get cameras: {resp.status}")
            data = await resp.json()
            return data.get("items", data) if isinstance(data, dict) else data

    async def get_snapshot(self, camera: str) -> bytes:
        async with self._session.get(
            f"{self._host}/api/cameras/{camera}/snapshot",
            headers=self._headers,
        ) as resp:
            if resp.status != 200:
                raise VedettaApiError(f"Failed to get snapshot: {resp.status}")
            return await resp.read()

    async def webrtc_offer(self, camera: str, sdp_offer: str) -> dict:
        async with self._session.post(
            f"{self._host}/api/cameras/{camera}/webrtc/offer",
            headers=self._headers,
            json={"type": "offer", "sdp": sdp_offer},
        ) as resp:
            if resp.status != 200:
                raise VedettaApiError(f"WebRTC offer failed: {resp.status}")
            return await resp.json()

    async def send_ptz(self, camera: str, command: str) -> None:
        async with self._session.post(
            f"{self._host}/api/cameras/{camera}/ptz",
            headers=self._headers,
            json={"command": command},
        ) as resp:
            if resp.status != 200:
                raise VedettaApiError(f"PTZ command failed: {resp.status}")

    async def get_events(
        self, camera: str | None = None, limit: int = 50
    ) -> list[dict]:
        params: dict[str, str] = {"limit": str(limit)}
        if camera:
            params["camera"] = camera
        async with self._session.get(
            f"{self._host}/api/events",
            headers=self._headers,
            params=params,
        ) as resp:
            if resp.status != 200:
                raise VedettaApiError(f"Failed to get events: {resp.status}")
            data = await resp.json()
            return data.get("items", data) if isinstance(data, dict) else data

    async def get_event_clip(self, event_id: str) -> bytes:
        async with self._session.get(
            f"{self._host}/api/events/{event_id}/clip",
            headers=self._headers,
        ) as resp:
            if resp.status != 200:
                raise VedettaApiError(f"Failed to get clip: {resp.status}")
            return await resp.read()

    async def get_event_thumbnail(self, event_id: str) -> bytes:
        async with self._session.get(
            f"{self._host}/api/events/{event_id}/detection-crop",
            headers=self._headers,
        ) as resp:
            if resp.status != 200:
                raise VedettaApiError(f"Failed to get thumbnail: {resp.status}")
            return await resp.read()

    async def get_recordings_calendar(self, camera: str) -> list[dict]:
        async with self._session.get(
            f"{self._host}/api/recordings/calendar",
            headers=self._headers,
            params={"camera": camera},
        ) as resp:
            if resp.status != 200:
                raise VedettaApiError(f"Failed to get calendar: {resp.status}")
            return await resp.json()

    async def get_recording_segments(
        self, camera: str, start: str, end: str
    ) -> list[dict]:
        async with self._session.get(
            f"{self._host}/api/recordings/segments",
            headers=self._headers,
            params={"camera": camera, "start": start, "end": end},
        ) as resp:
            if resp.status != 200:
                raise VedettaApiError(f"Failed to get segments: {resp.status}")
            return await resp.json()

    async def get_mjpeg_url(self, camera: str) -> str:
        return f"{self._host}/api/cameras/{camera}/mjpeg"
