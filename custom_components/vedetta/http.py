"""HTTP views that proxy Vedetta media streams through Home Assistant.

Vedetta only accepts bearer-token auth via the Authorization header. The
media browser cannot attach custom headers when the frontend plays back
media, so we expose authenticated HA views that stream the content from
Vedetta using the server-side API token.
"""

from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import VedettaCoordinator

_LOGGER = logging.getLogger(__name__)


def _coordinator(hass: HomeAssistant) -> VedettaCoordinator | None:
    data = hass.data.get(DOMAIN) or {}
    if not data:
        return None
    return next(iter(data.values()))


async def _proxy(
    request: web.Request,
    coordinator: VedettaCoordinator,
    upstream_url: str,
    default_mime: str,
) -> web.StreamResponse:
    """Stream bytes from Vedetta to the HA client with bearer auth."""
    session = coordinator.api._session
    headers = {"Authorization": f"Bearer {coordinator.api._token}"}

    async with session.get(upstream_url, headers=headers) as upstream:
        if upstream.status != 200:
            _LOGGER.warning(
                "Vedetta media proxy: upstream returned %s for %s",
                upstream.status,
                upstream_url,
            )
            return web.Response(
                status=502,
                text=f"upstream status {upstream.status}",
            )

        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": upstream.headers.get("Content-Type", default_mime),
                "Cache-Control": "no-cache",
            },
        )
        if content_length := upstream.headers.get("Content-Length"):
            response.headers["Content-Length"] = content_length
        await response.prepare(request)

        async for chunk in upstream.content.iter_chunked(64 * 1024):
            await response.write(chunk)

        await response.write_eof()
        return response


class VedettaClipView(HomeAssistantView):
    """Proxy an event clip."""

    url = "/api/vedetta/clip/{event_id}"
    name = "api:vedetta:clip"
    requires_auth = True

    async def get(self, request: web.Request, event_id: str) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        coordinator = _coordinator(hass)
        if coordinator is None:
            return web.Response(status=503, text="Vedetta integration not loaded")

        url = f"{coordinator.api._host}/api/events/{event_id}/clip"
        return await _proxy(request, coordinator, url, "video/mp4")


class VedettaExportView(HomeAssistantView):
    """Proxy a recording export (MP4 for a time range)."""

    url = "/api/vedetta/export/{camera}"
    name = "api:vedetta:export"
    requires_auth = True

    async def get(self, request: web.Request, camera: str) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        coordinator = _coordinator(hass)
        if coordinator is None:
            return web.Response(status=503, text="Vedetta integration not loaded")

        start = request.query.get("start", "")
        end = request.query.get("end", "")
        if not start or not end:
            return web.Response(status=400, text="start and end are required")

        url = (
            f"{coordinator.api._host}/api/recordings/export/{camera}"
            f"?start={start}&end={end}"
        )
        return await _proxy(request, coordinator, url, "video/mp4")


def async_register_views(hass: HomeAssistant) -> None:
    """Register HTTP views (idempotent — safe across reloads)."""
    if hass.data.get(f"{DOMAIN}_http_views_registered"):
        return
    hass.http.register_view(VedettaClipView())
    hass.http.register_view(VedettaExportView())
    hass.data[f"{DOMAIN}_http_views_registered"] = True
