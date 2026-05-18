# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Nachbarschaft-Laden** is a Home Assistant–based smart neighborhood EV charging station management system. It tracks charging sessions, displays dynamic electricity prices, visualizes photovoltaic (PV) surplus forecasts, and drives an e-paper display. There is no build system – this is a multi-module integration project deployed directly into a running Home Assistant environment.

## Deployment

Files are deployed via `deploy.ps1` (SCP to `root@nachbarschaft-laden.de`):

```powershell
.\deploy.ps1
```

| Source | Destination on HA host |
|---|---|
| `appdeamon/*.py` + `appdeamon/apps.yaml` | `/addon_configs/a0d7b954_appdaemon/apps/` |
| `www/` | `/homeassistant/www/nachbarschaftsladen/` |
| `epaper/display.yaml` | Flashed to ESP32 via ESPHome CLI |

**ESPHome commands:**
```bash
esphome compile epaper/display.yaml
esphome upload epaper/display.yaml
```

**No Python package manager or requirements file** – all Python dependencies (Pillow, AppDaemon) are provided by the Home Assistant AppDaemon add-on environment.

## Architecture & Data Flow

```
go-eCharger hardware (RFID + energy metering)
    → evcc (EV charging bridge)
        → Home Assistant sensors
            → AppDaemon Python apps
                ├── ladeSession.py      → sessions.json
                └── ladepreis_graph.py  → data.json + display_combined.png
                        ↑                         ↓
                  HA sensor events       ESPHome e-paper display (partial 5s / full 60s)
                                                  ↓
                                     www/index.html + www/sessions.html (browser fetches JSON)
```

All runtime output lands in `/homeassistant/www/nachbarschaftsladen/` on the HA host. The web UIs are pure client-side HTML/JS – no bundler, no framework.

## AppDaemon Apps

Both apps live in `appdeamon/` and inherit from `hassapi.Hass`.

### `ladeSession.py` – Charging Session Tracker

- Fires on state changes of `binary_sensor.evcc_go_echarger_ocpp_charging` and several `sensor.evcc_go_echarger_ocpp_session_*` entities.
- Reads the active RFID card from `select.go_echarger_XXXXXX_trx` and maps it to a human name via the `RFID_USERS` dict (currently empty – fill in `"CARD_ID": "Name"` entries to enable user attribution).
- Appends completed sessions to `sessions.json`; rotates at 500 entries (FIFO).
- Ignores sessions under 0.1 kWh.
- Uses atomic write (write to `.tmp`, then `os.replace`) for JSON files.

### `ladepreis_graph.py` – Pricing & PV Visualization

- Fires on state changes of `sensor.expgldurchschnitt_ema_asymalpha` (electricity price in ¢/kWh, EMA-smoothed) and three PV forecast sensors (`sensor.morgenpv`, `sensor.uebermorgenpv`, `sensor.pvin3tagen`).
- Writes `data.json` with current price, 8-hour smoothed price history (15-min buckets, only prices in 10–40 ¢/kWh range stored), peak-hours (13–19h) average, and 3-day PV surplus forecasts.
- Generates two images:
  - `display_combined.png` (`/homeassistant/www/`) – 460×160px, 1-bit invertiertes Smiley-PNG für das E-Paper (3 Smileys nebeneinander)
  - `display_preview.png` (`/homeassistant/www/nachbarschaftsladen/`) – 480×800px RGB-PNG mit dem vollständigen Display-Layout (Ladepreis, Smileys, kWh-Werte, Uhrzeit, QR-Code, Logo) zur Spiegelung in HA
- Smiley face mood is determined by PV surplus thresholds: <15 kW sad, 15–32 kW neutral, 32–50 kW happy, >50 kW very happy.

## Web Frontends

Both are standalone HTML files with embedded CSS and JS – no build step.

- **`www/index.html`** – Main dashboard: current price vs. daily average, best charging time, savings calculator, 8-hour price trend, 3-day PV smiley forecast.
- **`www/sessions.html`** – Charging history: filterable/searchable table with aggregate statistics, user filter (auto-populated), date range selector, solar percentage badges.

Both fetch JSON via `fetch()` from relative URLs pointing to the HA web server.

## Key Configuration Constants

| File | Constant | Meaning |
|---|---|---|
| `ladeSession.py` | `RFID_USERS` | Maps RFID card IDs → display names |
| `ladepreis_graph.py` | `Y_MIN / Y_MAX` | Price range stored in history (¢/kWh) |
| `ladepreis_graph.py` | `SMOOTH_MINUTES = 15` | Price history bucket size |
| `epaper/display.yaml` | `url:` in `http_request` | HA base URL for image pulls |

## Language

All UI text, variable names, comments, and entity names are in German. Keep this convention when editing.
