"""Vedetta media source — hierarchical browse for events and recordings."""

from __future__ import annotations

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_get_media_source(hass: HomeAssistant) -> VedettaMediaSource:
    """Return the VedettaMediaSource instance for the first config entry."""
    entry_id = next(iter(hass.data[DOMAIN]))
    coordinator = hass.data[DOMAIN][entry_id]
    return VedettaMediaSource(hass, coordinator)


class VedettaMediaSource(MediaSource):
    """Hierarchical media browser for Vedetta events and recordings."""

    name = "Vedetta"

    def __init__(self, hass: HomeAssistant, coordinator) -> None:
        super().__init__(DOMAIN)
        self.hass = hass
        self._coordinator = coordinator

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a playable item to a URL or stream."""
        identifier = item.identifier

        if identifier.startswith("clip/"):
            event_id = identifier[len("clip/"):]
            # Proxy through the HA integration to add bearer auth server-side.
            return PlayMedia(
                url=f"/api/vedetta/clip/{event_id}",
                mime_type="video/mp4",
            )

        if identifier.startswith("day/"):
            # day/{camera}/{YYYY-MM-DD}
            parts = identifier.split("/", 2)
            _, camera, day = parts
            start = f"{day}T00:00:00Z"
            end = f"{day}T23:59:59Z"
            return PlayMedia(
                url=f"/api/vedetta/export/{camera}?start={start}&end={end}",
                mime_type="video/mp4",
            )

        raise ValueError(f"Cannot resolve media identifier: {identifier}")

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return a browse tree node for the given identifier."""
        identifier = item.identifier if item.identifier else ""

        if not identifier:
            return self._browse_root()

        parts = identifier.split("/")

        if parts[0] == "events":
            if len(parts) == 1:
                return self._browse_events_root()
            camera = parts[1]
            return await self._browse_events_for_camera(camera)

        if parts[0] == "recordings":
            if len(parts) == 1:
                return self._browse_recordings_root()
            camera = parts[1]
            return await self._browse_recordings_calendar(camera)

        raise ValueError(f"Unknown media source identifier: {identifier}")

    # ------------------------------------------------------------------
    # Private browse helpers
    # ------------------------------------------------------------------

    def _browse_root(self) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title="Vedetta",
            can_play=False,
            can_expand=True,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="events",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.VIDEO,
                    title="Events",
                    can_play=False,
                    can_expand=True,
                ),
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="recordings",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.VIDEO,
                    title="Recordings",
                    can_play=False,
                    can_expand=True,
                ),
            ],
        )

    def _browse_events_root(self) -> BrowseMediaSource:
        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"events/{cam['name']}",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.VIDEO,
                title=cam["name"],
                can_play=False,
                can_expand=True,
            )
            for cam in self._coordinator.cameras
        ]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="events",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title="Events",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _browse_events_for_camera(self, camera: str) -> BrowseMediaSource:
        events = await self._coordinator.api.get_events(camera=camera, limit=50)
        children = []
        for event in events:
            event_id = event.get("id", "")
            timestamp = event.get("timestamp", event.get("start_time", ""))
            label = event.get("label", "unknown")
            score = event.get("score", 0)
            score_pct = int(score * 100) if isinstance(score, float) else score
            title = f"{timestamp} - {label} ({score_pct}%)"
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"clip/{event_id}",
                    media_class=MediaClass.VIDEO,
                    media_content_type=MediaType.VIDEO,
                    title=title,
                    can_play=True,
                    can_expand=False,
                )
            )
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"events/{camera}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=camera,
            can_play=False,
            can_expand=True,
            children=children,
        )

    def _browse_recordings_root(self) -> BrowseMediaSource:
        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"recordings/{cam['name']}",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.VIDEO,
                title=cam["name"],
                can_play=False,
                can_expand=True,
            )
            for cam in self._coordinator.cameras
        ]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="recordings",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title="Recordings",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _browse_recordings_calendar(self, camera: str) -> BrowseMediaSource:
        # Query the current month. Vedetta's calendar returns day numbers
        # (1-31) for the month that have recordings.
        today = dt_util.now().date()
        month = today.strftime("%Y-%m")
        days = await self._coordinator.api.get_recordings_calendar(camera, month)
        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"day/{camera}/{today.replace(day=day).isoformat()}",
                media_class=MediaClass.VIDEO,
                media_content_type=MediaType.VIDEO,
                title=today.replace(day=day).isoformat(),
                can_play=True,
                can_expand=False,
            )
            for day in sorted(days, reverse=True)
        ]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"recordings/{camera}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=camera,
            can_play=False,
            can_expand=True,
            children=children,
        )
