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
            url = (
                f"{self._coordinator.api._host}/api/events/{event_id}/clip"
                f"?token={self._coordinator.api._token}"
            )
            return PlayMedia(url=url, mime_type="video/mp4")

        if identifier.startswith("segment/"):
            # segment/{camera}/{start}/{end}
            parts = identifier.split("/", 3)
            _, camera, start, end = parts
            url = (
                f"{self._coordinator.api._host}/api/recordings/hls"
                f"?camera={camera}&start={start}&end={end}"
                f"&token={self._coordinator.api._token}"
            )
            return PlayMedia(url=url, mime_type="application/x-mpegURL")

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
            if len(parts) == 2:
                return await self._browse_recordings_calendar(camera)
            date = parts[2]
            return await self._browse_recording_segments(camera, date)

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
        calendar = await self._coordinator.api.get_recordings_calendar(camera)
        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"recordings/{camera}/{entry['date']}",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.VIDEO,
                title=entry["date"],
                can_play=False,
                can_expand=True,
            )
            for entry in calendar
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

    async def _browse_recording_segments(
        self, camera: str, date: str
    ) -> BrowseMediaSource:
        # Use date boundaries: date 00:00 to date+1 00:00
        start = f"{date}T00:00:00"
        end = f"{date}T23:59:59"
        segments = await self._coordinator.api.get_recording_segments(
            camera, start, end
        )
        children = []
        for segment in segments:
            seg_start = segment.get("start", "")
            seg_end = segment.get("end", "")
            title = f"{seg_start} – {seg_end}"
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"segment/{camera}/{seg_start}/{seg_end}",
                    media_class=MediaClass.VIDEO,
                    media_content_type=MediaType.VIDEO,
                    title=title,
                    can_play=True,
                    can_expand=False,
                )
            )
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"recordings/{camera}/{date}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=date,
            can_play=False,
            can_expand=True,
            children=children,
        )
