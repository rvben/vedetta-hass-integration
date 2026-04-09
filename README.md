# Vedetta for Home Assistant

A Home Assistant custom integration for [Vedetta](https://github.com/rvben/vedetta) NVR.

Provides native Home Assistant entities for Vedetta cameras, detections, zones,
and recordings — including live WebRTC streams, detection events, PTZ controls,
and a media browser for event clips and full-day recording playback.

## Features

- **Camera entities** with WebRTC live streaming and on-demand snapshots
- **Binary sensors** for system availability, camera online/offline, object counts per camera per label, and zone presence
- **Event entities** that fire `detection_start` and `detection_end` for automation triggers
- **Image entities** showing the latest detection snapshot per camera
- **PTZ buttons** (pan/tilt/zoom) for PTZ-capable cameras
- **Media browser** with event clips and day-scoped recording playback, streamed through authenticated HA proxy views (no token leakage)
- **Dynamic discovery** of object labels and zones from MQTT — new sensors appear automatically as Vedetta publishes them
- **MQTT-driven** state (no polling) with retained topics for instant recovery on HA restart

## Requirements

- Home Assistant 2024.4 or later
- Vedetta NVR reachable over HTTP from your HA instance
- The [MQTT integration](https://www.home-assistant.io/integrations/mqtt/) configured in Home Assistant, using the **same broker** that Vedetta publishes to
- A Vedetta API token with sufficient scopes (use `*` or include `api:read`, `api:write`, and `camera:ptz` as needed)

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant → **⋮** → **Custom repositories**
2. Add `https://github.com/rvben/vedetta-hass-integration` as an **Integration**
3. Search for **Vedetta** in HACS and install
4. Restart Home Assistant

### Manual

Copy `custom_components/vedetta/` to your Home Assistant config directory (so it ends up at `<config>/custom_components/vedetta/`) and restart Home Assistant.

## Configuration

1. In Home Assistant go to **Settings → Devices & Services → Add Integration**
2. Search for **Vedetta**
3. Enter:
   - **URL** — your Vedetta instance, e.g. `http://192.168.1.180:5050`
   - **API Token** — a long-lived token generated in Vedetta's API (`POST /api/tokens`)
   - **MQTT Topic Prefix** — defaults to `vedetta`, matching Vedetta's default `mqtt.topic`

The config flow validates the connection via `/api/health` before creating the entry.

### Disable Vedetta's built-in MQTT discovery

Vedetta publishes its own Home Assistant MQTT auto-discovery messages by
default, which duplicates what this integration creates. After installing the
integration, set `ha_discovery: false` in your Vedetta config to avoid
duplicate entities.

## Entities

Per camera (using `front_door` as an example):

| Entity | Description |
|--------|-------------|
| `camera.front_door` | Live WebRTC stream + snapshots |
| `image.front_door_last_detection` | Latest detection snapshot |
| `event.front_door_detection` | Fires `detection_start`/`detection_end` with label, score, zone, box |
| `binary_sensor.front_door_status` | Online/offline |
| `binary_sensor.front_door_{label}` | Object count > 0 (person, car, dog, etc.) — created dynamically |
| `button.front_door_ptz_{direction}` | PTZ control (only for PTZ cameras) |

Global:

| Entity | Description |
|--------|-------------|
| `binary_sensor.vedetta_nvr_availability` | Vedetta online/offline via MQTT LWT |
| `binary_sensor.vedetta_nvr_zone_{zone}_{label}` | Zone presence (created dynamically) |

## Architecture

This integration mirrors the Frigate HA integration pattern: **MQTT for real-time
state, HTTP API for on-demand content, WebRTC for live streams.** MQTT
subscriptions drive all entity state updates — the integration never polls
Vedetta. The HTTP API is used for camera snapshots, media browser content,
PTZ commands, and config flow validation.

Event clips and recording exports are streamed through authenticated Home
Assistant views so the Vedetta API token is never exposed to the browser or
media player.

## Development

```sh
make test   # run pytest
make lint   # run ruff
```

## License

MIT
