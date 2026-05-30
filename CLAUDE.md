# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Nachbarschaft-Laden** is a Home Assistant–based smart neighborhood EV charging station management system. It tracks charging sessions, displays dynamic electricity prices, visualizes photovoltaic (PV) surplus forecasts, and drives an e-paper display. There is no build system – this is a multi-module integration project deployed as a Home Assistant add-on.

## Repository Structure

```
addon/          ← einzige Quelle für das HA-Add-on
  apps/         ← AppDaemon Python-Apps (ladeSession.py, ladepreis_graph.py)
  www/          ← Web-Frontend (HTML/CSS/JS, robots.txt, SVG)
  Dockerfile
  run.sh        ← Startet AppDaemon, kopiert www/ nach /homeassistant/www/nachbarschaft-laden/
  config.yaml
  icon.png
  logo.png
epaper/         ← ESPHome-Konfiguration für E-Paper-Display (display.yaml + secrets.yaml)
ha-integrations/ ← HA-Vorlagen (YAML) für Sensoren/Helfer
docs/           ← GitHub Pages (statische Demo-Seite)
```

## Deployment

```powershell
.\deploy.ps1          # Add-on rebuild (nach git push)
.\deploy.ps1 hotdeploy  # Python-Apps direkt hot-deployen (kein Docker-Rebuild)
```

| Was | Wie |
|---|---|
| Add-on (HTML, Python, run.sh) | `deploy.ps1` → store-reload + rebuild via HA Supervisor |
| Python-Apps (ohne Rebuild) | `deploy.ps1 hotdeploy` → SCP nach `/homeassistant/.addon_nachbarschaft_laden/apps/` |
| Web-Frontend only | SCP `addon/www/*.html` nach `/homeassistant/www/nachbarschaft-laden/` |
| E-Paper-Firmware | `esphome compile/upload epaper/display.yaml` |

**Laufzeit-Output** (von `run.sh` bei Add-on-Start geschrieben):
- HTML/statische Dateien: `/homeassistant/www/nachbarschaft-laden/` (serviert als `/local/nachbarschaft-laden/`)
- Python-Apps: `/homeassistant/.addon_nachbarschaft_laden/apps/`

**HA-Host**: 192.168.198.25, SSH-User: root

**No Python package manager or requirements file** – all Python dependencies (Pillow, AppDaemon) are installed in the Dockerfile.

## Architecture & Data Flow

```
go-eCharger hardware (RFID + energy metering)
    → Home Assistant sensors
        → AppDaemon Python apps
            ├── ladeSession.py      → sessions.json, balances.json
            └── ladepreis_graph.py  → data.json + price_history.json
                                    → display_combined.png (Smiley-Bild)
                                    → display_preview.png (Vorschau-PNG)
                                    → input_number.nl_surplus_* (HA-Helper)
                                    → sensor.nl_ladepreis_aktuell (HA-Sensor)
                                              ↓
                              ESPHome e-paper display
                              - partial refresh alle 5s
                              - full refresh alle 10min (120 × 5s)
                              - Nachtmodus 22–6h: alle 30min
                                              ↓
                         addon/www/index.html + sessions.html (browser fetches JSON)
```

All runtime output lands in `/homeassistant/www/nachbarschaft-laden/` on the HA host. The web UIs are pure client-side HTML/JS – no bundler, no framework.

## AppDaemon Apps

Both apps live in `addon/apps/` and inherit from `hassapi.Hass`.

### `ladeSession.py` – Charging Session Tracker

- Fires on state changes of the charger status sensor and session sensors.
- Reads the active RFID card and maps it to a human name via the `rfid_benutzer` config.
- Appends completed sessions to `sessions.json`; rotates at 500 entries (FIFO).
- Ignores sessions under 0.1 kWh.
- Uses atomic write (write to `.tmp`, then `os.replace`) for JSON files.

### `ladepreis_graph.py` – Pricing & PV Visualization

- Runs every 5 minutes (`run_every`) and on charger status changes.
- Calculates dynamic charging price from 3 power sensors (grid, wallbox, battery).
- Publishes `sensor.nl_ladepreis_aktuell` to HA via `set_state`.
- Writes PV surplus values to `input_number.nl_surplus_morgen/uebermorgen/in3tagen` via `call_service` (persists across HA restarts).
- Writes `data.json` with: current price, 6h smoothed history (15-min buckets), 72h long history (60-min buckets), peak-hours average, 3-day PV surplus forecasts, best charging hours.
- Stores up to 2 weeks (336h) of raw price history in `price_history.json`.
- Generates two images:
  - `display_combined.png` – 460×136px, 1-bit invertiertes Smiley-PNG für das E-Paper
  - `display_preview.png` – 480×800px RGB-PNG mit dem vollständigen Display-Layout zur Spiegelung in HA
- Smiley face mood: <15 kWh sad, 15–32 kWh neutral, 32–50 kWh happy, >50 kWh very happy.

## Web Frontends

Standalone HTML files with embedded CSS and JS – no build step. Source in `addon/www/`.

- **`index.html`** – Main dashboard: current price, best charging time (today + forecast), savings calculator, 6h price sparkline, 72h price chart, 3-day PV smiley forecast, active session info.
- **`sessions.html`** – Charging history: filterable/searchable table with aggregate statistics, user filter, date range selector, solar percentage badges.
- **`display.html`** – E-Paper display documentation page.
- **`display_preview_viewer.html`** – Live preview of the e-paper display_preview.png.

## E-Paper Display (epaper/display.yaml)

ESPHome configuration for Waveshare 7.5" V2p on ESP32.

**Key entities published to HA:**
- `sensor.display_wi_fi_signal` – RSSI in dBm
- `sensor.display_uptime` – seconds since boot
- `button.display_display_sofort_refresh` – force image reload + full refresh

**HA helpers read by display:**
- `input_number.nl_surplus_morgen/uebermorgen/in3tagen` – PV surplus forecasts
- `sensor.nl_ladepreis_aktuell` – current charging price
- `input_boolean.nl_display_pause` – pause mode toggle
- `input_text.nl_display_pause_text` – pause screen text (max 60 chars, auto word-wrap)

**Timing:**
- `update_interval: 5s` + `full_update_every: 120` → partial every 5s, full every 10min
- Night mode (22–6h): skips 359 of 360 render calls → effectively every 30min

**Secrets file** (`epaper/secrets.yaml`, NOT in repo):
```yaml
wifi_ssid, wifi_password, api_encryption_key, ota_password, ap_password,
epaper_display_image_url, epaper_qr_url
```

## Key Configuration Constants

| File | Constant | Meaning |
|---|---|---|
| `addon/apps/ladepreis_graph.py` | `Y_MIN / Y_MAX` | Price range stored in history (ct/kWh) |
| `addon/apps/ladepreis_graph.py` | `SMOOTH_MINUTES = 15` | Price history bucket size |
| `addon/apps/ladepreis_graph.py` | `HISTORY_HOURS = 336` | Raw history retention (2 weeks) |
| `addon/apps/ladepreis_graph.py` | `DISPLAY_HOURS = 72` | Window exported to data.json |
| `addon/apps/ladepreis_graph.py` | `PREIS_TOTZONE_KW = 0.5` | Deadband below which max price applies |
| `epaper/display.yaml` | `full_update_every: 120` | Full refresh interval (× 5s = 10min) |

## Language

All UI text, variable names, comments, and entity names are in German. Keep this convention when editing.

## Important: After every change

Deploy immediately after committing:
- Python-App changes: `scp addon/apps/ladepreis_graph.py root@192.168.198.25:/homeassistant/.addon_nachbarschaft_laden/apps/`
- HTML changes: `scp addon/www/*.html root@192.168.198.25:/homeassistant/www/nachbarschaft-laden/`
- ESPHome changes: compile + upload via ESPHome CLI or dashboard
