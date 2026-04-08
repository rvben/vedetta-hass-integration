"""Tests for the Vedetta media source browser."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.vedetta.media_source import VedettaMediaSource


def _make_source(cameras: list[dict] | None = None) -> VedettaMediaSource:
    """Construct a VedettaMediaSource with a mock coordinator."""
    if cameras is None:
        cameras = [{"name": "front-door"}, {"name": "backyard"}]

    coordinator = MagicMock()
    coordinator.cameras = cameras
    coordinator.api = AsyncMock()
    coordinator.api._host = "http://nvr.local:5050"
    coordinator.api._token = "test-token"

    hass = MagicMock()
    source = VedettaMediaSource(hass, coordinator)
    return source


def _make_item(identifier: str | None) -> MagicMock:
    item = MagicMock()
    item.identifier = identifier
    return item


# ---------------------------------------------------------------------------
# Root browse
# ---------------------------------------------------------------------------


async def test_browse_root() -> None:
    """Root node must have exactly two children: Events and Recordings."""
    source = _make_source()
    result = await source.async_browse_media(_make_item(None))

    assert result.title == "Vedetta"
    assert result.can_expand is True
    assert result.can_play is False
    assert len(result.children) == 2
    titles = {child.title for child in result.children}
    assert titles == {"Events", "Recordings"}


async def test_browse_root_children_identifiers() -> None:
    """Root children must carry the correct identifiers."""
    source = _make_source()
    result = await source.async_browse_media(_make_item(""))

    identifiers = {child.identifier for child in result.children}
    assert "events" in identifiers
    assert "recordings" in identifiers


# ---------------------------------------------------------------------------
# Events — camera list
# ---------------------------------------------------------------------------


async def test_browse_events_cameras() -> None:
    """Browsing 'events' returns one child per camera."""
    cameras = [{"name": "front-door"}, {"name": "backyard"}, {"name": "garage"}]
    source = _make_source(cameras)
    result = await source.async_browse_media(_make_item("events"))

    assert result.identifier == "events"
    assert result.can_expand is True
    assert len(result.children) == 3
    names = {child.title for child in result.children}
    assert names == {"front-door", "backyard", "garage"}


async def test_browse_events_cameras_identifiers() -> None:
    """Each camera child uses 'events/{name}' as its identifier."""
    source = _make_source([{"name": "front-door"}, {"name": "backyard"}])
    result = await source.async_browse_media(_make_item("events"))

    identifiers = {child.identifier for child in result.children}
    assert identifiers == {"events/front-door", "events/backyard"}


# ---------------------------------------------------------------------------
# Events — event list for a camera
# ---------------------------------------------------------------------------


async def test_browse_events_for_camera() -> None:
    """Browsing 'events/{camera}' returns one child per event from the API."""
    source = _make_source([{"name": "front-door"}])
    source._coordinator.api.get_events = AsyncMock(
        return_value=[
            {"id": "evt-1", "timestamp": "2026-04-08T10:00:00", "label": "person", "score": 0.92},
            {"id": "evt-2", "timestamp": "2026-04-08T11:30:00", "label": "car", "score": 0.75},
        ]
    )

    result = await source.async_browse_media(_make_item("events/front-door"))

    source._coordinator.api.get_events.assert_called_once_with(
        camera="front-door", limit=50
    )
    assert result.identifier == "events/front-door"
    assert len(result.children) == 2

    first = result.children[0]
    assert first.identifier == "clip/evt-1"
    assert first.can_play is True
    assert first.can_expand is False
    assert "person" in first.title
    assert "92%" in first.title

    second = result.children[1]
    assert second.identifier == "clip/evt-2"
    assert "car" in second.title
    assert "75%" in second.title


async def test_browse_events_for_camera_empty() -> None:
    """An empty event list results in a valid node with no children."""
    source = _make_source([{"name": "front-door"}])
    source._coordinator.api.get_events = AsyncMock(return_value=[])

    result = await source.async_browse_media(_make_item("events/front-door"))

    assert result.children == []


# ---------------------------------------------------------------------------
# Recordings — camera list
# ---------------------------------------------------------------------------


async def test_browse_recordings_cameras() -> None:
    """Browsing 'recordings' returns one child per camera."""
    cameras = [{"name": "front-door"}, {"name": "backyard"}]
    source = _make_source(cameras)
    result = await source.async_browse_media(_make_item("recordings"))

    assert result.identifier == "recordings"
    assert result.can_expand is True
    assert len(result.children) == 2
    identifiers = {child.identifier for child in result.children}
    assert identifiers == {"recordings/front-door", "recordings/backyard"}


# ---------------------------------------------------------------------------
# Recordings — calendar dates for a camera
# ---------------------------------------------------------------------------


async def test_browse_recordings_calendar() -> None:
    """Browsing 'recordings/{camera}' returns date nodes from the API."""
    source = _make_source([{"name": "front-door"}])
    source._coordinator.api.get_recordings_calendar = AsyncMock(
        return_value=[
            {"date": "2026-04-08"},
            {"date": "2026-04-07"},
        ]
    )

    result = await source.async_browse_media(_make_item("recordings/front-door"))

    source._coordinator.api.get_recordings_calendar.assert_called_once_with(
        "front-door"
    )
    assert len(result.children) == 2
    dates = {child.title for child in result.children}
    assert dates == {"2026-04-08", "2026-04-07"}
    assert result.children[0].identifier == "recordings/front-door/2026-04-08"


# ---------------------------------------------------------------------------
# Recordings — segments for a date
# ---------------------------------------------------------------------------


async def test_browse_recording_segments() -> None:
    """Browsing 'recordings/{camera}/{date}' returns playable segment nodes."""
    source = _make_source([{"name": "front-door"}])
    source._coordinator.api.get_recording_segments = AsyncMock(
        return_value=[
            {"start": "2026-04-08T08:00:00", "end": "2026-04-08T08:15:00"},
            {"start": "2026-04-08T09:00:00", "end": "2026-04-08T09:30:00"},
        ]
    )

    result = await source.async_browse_media(
        _make_item("recordings/front-door/2026-04-08")
    )

    source._coordinator.api.get_recording_segments.assert_called_once_with(
        "front-door", "2026-04-08T00:00:00", "2026-04-08T23:59:59"
    )
    assert len(result.children) == 2
    first = result.children[0]
    assert first.can_play is True
    assert first.can_expand is False
    assert "2026-04-08T08:00:00" in first.identifier
    assert first.identifier.startswith("segment/front-door/")


# ---------------------------------------------------------------------------
# Resolve media
# ---------------------------------------------------------------------------


async def test_resolve_clip() -> None:
    """Resolving a clip identifier returns a video/mp4 PlayMedia."""
    source = _make_source()
    item = _make_item("clip/evt-abc")
    result = await source.async_resolve_media(item)

    assert result.mime_type == "video/mp4"
    assert "evt-abc" in result.url
    assert "nvr.local" in result.url


async def test_resolve_segment() -> None:
    """Resolving a segment identifier returns an HLS PlayMedia."""
    source = _make_source()
    item = _make_item("segment/front-door/2026-04-08T08:00:00/2026-04-08T08:15:00")
    result = await source.async_resolve_media(item)

    assert result.mime_type == "application/x-mpegURL"
    assert "front-door" in result.url
    assert "nvr.local" in result.url


async def test_resolve_unknown_raises() -> None:
    """Resolving an unknown identifier raises ValueError."""
    source = _make_source()
    item = _make_item("bogus/identifier")
    with pytest.raises(ValueError):
        await source.async_resolve_media(item)
