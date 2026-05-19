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
epaper/         ← ESPHome-Konfiguration für E-Paper-Display
ha-integrations/ ← HA-Vorlagen (YAML) für Sensoren/Helfer
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
| E-Paper-Firmware | `esphome compile/upload epaper/display.yaml` |

**Laufzeit-Output** (von `run.sh` bei Add-on-Start geschrieben):
- HTML/statische Dateien: `/homeassistant/www/nachbarschaft-laden/` (serviert als `/local/nachbarschaft-laden/`)
- Python-Apps: `/homeassistant/.addon_nachbarschaft_laden/apps/`

**No Python package manager or requirements file** – all Python dependencies (Pillow, AppDaemon) are installed in the Dockerfile.

## Architecture & Data Flow

```
go-eCharger hardware (RFID + energy metering)
    → Home Assistant sensors
        → AppDaemon Python apps
            ├── ladeSession.py      → sessions.json
            └── ladepreis_graph.py  → data.json + display_combined.png
                    ↑                         ↓
              HA sensor events       ESPHome e-paper display (partial 5s / full 60s)
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

- Fires on state changes of the electricity price sensor (¢/kWh, EMA-smoothed) and PV forecast sensors.
- Writes `data.json` with current price, 8-hour smoothed price history (15-min buckets), peak-hours (13–19h) average, and 3-day PV surplus forecasts.
- Generates two images:
  - `display_combined.png` – 460×160px, 1-bit invertiertes Smiley-PNG für das E-Paper
  - `display_preview.png` – 480×800px RGB-PNG mit dem vollständigen Display-Layout zur Spiegelung in HA
- Smiley face mood is determined by PV surplus thresholds: <15 kW sad, 15–32 kW neutral, 32–50 kW happy, >50 kW very happy.

## Web Frontends

Standalone HTML files with embedded CSS and JS – no build step. Source in `addon/www/`.

- **`index.html`** – Main dashboard: current price vs. daily average, best charging time, savings calculator, 8-hour price trend, 3-day PV smiley forecast.
- **`sessions.html`** – Charging history: filterable/searchable table with aggregate statistics, user filter, date range selector, solar percentage badges.

## Key Configuration Constants

| File | Constant | Meaning |
|---|---|---|
| `addon/apps/ladeSession.py` | `RFID_USERS` | Maps RFID card IDs → display names |
| `addon/apps/ladepreis_graph.py` | `Y_MIN / Y_MAX` | Price range stored in history (¢/kWh) |
| `addon/apps/ladepreis_graph.py` | `SMOOTH_MINUTES = 15` | Price history bucket size |
| `epaper/display.yaml` | `url:` in `http_request` | HA base URL for image pulls |

## Language

All UI text, variable names, comments, and entity names are in German. Keep this convention when editing.
