# Nachbarschaft-Laden

[🇩🇪 Deutsch](#nachbarschaft-laden) · [🇬🇧 English](#nachbarschaft-laden-english)

> **Frühes Entwicklungsstadium** — Dieses Projekt steckt noch in den Kinderschuhen. Der Ersteller ist kein professioneller Entwickler; der Code ist gewachsen, nicht geplant. Fehler sind wahrscheinlich, Verbesserungen willkommen.
> Wer das Projekt übernehmen, forken oder als Basis für eigene Ideen nutzen möchte – nur zu. Ein Stern oder ein kurzes Hallo freut mich trotzdem. 🙂
>
> **Early stage** — This project is in its very early days. The creator is not a professional developer; the code grew organically rather than being planned. Bugs are likely, improvements are welcome.
> Feel free to fork it, take it over, or use it as a starting point for your own ideas. A star or a quick hello is always appreciated. 🙂

Home Assistant Add-on für die Verwaltung einer nachbarschaftlichen EV-Ladestation. Es berechnet einen dynamischen Ladepreis aus dem aktuellen PV-Überschuss, zeichnet Ladesessions auf und zeigt alles auf einer Webseite und einem E-Paper-Display an.

**[→ Live-Demo mit Beispieldaten ansehen](https://bernd780.github.io/Nachbarschaft-Laden/)**

---

## Für wen ist das?

Du hast eine PV-Anlage, eine Wallbox – und Nachbarn, die gerne günstiger laden würden?

**Nachbarschaft-Laden** macht genau das möglich: Der Ladepreis sinkt automatisch, wenn gerade viel Sonne scheint. Per RFID-Karte wird jeder Ladevorgang einem Nutzer zugeordnet und abgerechnet. Kein Cloud-Dienst, keine Abonnements – alles läuft lokal in Home Assistant.

<p align="center">
  <img src="docs/flyer_instagram.png" width="480" alt="Nachbarschaft-Laden Projektübersicht"/>
</p>

---

## Screenshots

### Web-Dashboard

Der aktuelle Ladepreis, der Tagesverlauf und die PV-Prognose für die nächsten drei Tage – alles auf einen Blick im Browser, ohne App.

<p align="center">
  <img src="docs/mockup_startseite.png" width="280" alt="Web-Dashboard Startseite"/>
</p>

- **Grün** = günstiger Preis (viel PV-Überschuss)
- **Gelb** = mittlerer Preis
- **Rot** = teurer Preis (Netzbezug)
- Die **beste Ladezeit** des Tages wird automatisch berechnet und hervorgehoben

### E-Paper-Display

Ein Waveshare 7,5"-Display am Eingang zeigt immer den aktuellen Ladepreis, die PV-Prognose als Smiley-Skala und den laufenden Ladevorgang an – auch ohne Smartphone oder Browser.

<p align="center">
  <img src="docs/foto_epaper.jpg" width="360" alt="E-Paper-Display in Betrieb"/>
</p>

<p align="center">
  <img src="docs/mockup_epaper.png" width="240" alt="E-Paper-Display Vorschau (generiert)"/>
</p>

Das Display zeigt auf einen Blick alles, was Nachbarn am Ladepunkt wissen müssen:

**Oben:** Der aktuelle Ladepreis in ct/kWh – groß und gut lesbar, auch aus etwas Entfernung.

**Mitte:** Die PV-Überschuss-Prognose als Smiley-Skala für die nächsten drei Tage, jeweils mit dem erwarteten Ertrag in kWh:
- **😄 Sehr glücklich** = voller PV-Überschuss, günstigster Preis
- **🙂 Glücklich** = guter Überschuss
- **😐 Neutral** = gemischte Bedingungen
- **😞 Traurig** = wenig PV, hoher Netzanteil

**Unten:** Uhrzeit und Datum, ein QR-Code direkt zur Weboberfläche mit dem Preisverlauf und dem Ladeprotokoll sowie das Projektlogo.

Das Display aktualisiert sich alle 60 Sekunden automatisch (alle 5 Sekunden partiell). Es läuft auf einem ESP32 via ESPHome, zieht das Bild direkt von Home Assistant und benötigt keinen eigenen Server.

---

## Funktionen

- **Dynamischer Ladepreis** – berechnet in Echtzeit aus Netzleistung, Wallbox-Leistung und Batterieentladung
- **Preisverlauf** – 72-Stunden-Aufzeichnung, geglättet in 15-Minuten-Buckets
- **PV-Prognose** – 3-Tages-Vorschau als Smiley-Skala (traurig bis sehr glücklich)
- **Session-Tracking** – Energie, Kosten, Dauer und Nutzer (per RFID) je Ladevorgang
- **Saldo-Verwaltung** – offene Beträge je Nutzer, Zahlung über HA-Helfer buchbar
- **Weboberfläche** – `index.html` (Preis-Dashboard) und `sessions.html` (Ladeverlauf)
- **E-Paper-Display** – 460×160 Smiley-Bild für Waveshare 7,5" via ESPHome

---

## Installation

### Voraussetzungen

- Home Assistant OS oder Supervised
- go-eCharger mit HA-Integration
- PV-Anlage mit Echtzeit-Leistungssensor

### Add-on installieren

1. Den Ordner `addon/` auf den HA-Host kopieren, z. B. nach `/addons/nachbarschaft-laden/`
2. In HA: **Einstellungen → Add-ons → Add-on-Store → ⋮ → Lokale Add-ons neu laden**
3. „Nachbarschaft-Laden" unter „Lokale Add-ons" → **Installieren → Starten**

### Hilfsfelder

Es sind **keine HA-Helfer nötig**. Das Add-on verwaltet alle Zwischenwerte intern:

- Session-Startwerte (Zählerstand, Kosten-Integral) werden in `session_active.json` gespeichert
- Hausverbrauch und Ladeziels-SOC sind feste Werte in der Add-on-Konfiguration

---

## Konfiguration

Nach der Installation: **Add-on → Konfiguration**. Alle Felder haben sinnvolle Voreinstellungen.

### Ladepreis-Berechnung

Das Add-on berechnet den Preis direkt aus drei Leistungssensoren. Kein externer Preissensor nötig.

#### Eingangssensoren

| Option | Bedeutung | Voreinstellung |
|---|---|---|
| `sensor_netzleistung` | Netzleistung am Hauptzähler in W (positiv = Bezug, negativ = Einspeisung) | `sensor.leistung_stromzaehler` |
| `sensor_wallbox_leistung` | Aktuelle Ladeleistung der Wallbox in W | `sensor.go_echarger_XXXXXX_nrg_12` |
| `sensor_batterie_leistung` | Aktuelle Batterieentladungsleistung in W (positiv = Entladung) | `sensor.summe_battery_leistung` |

#### Preiskonstanten

| Option | Bedeutung | Voreinstellung |
|---|---|---|
| `preis_einspeiseverguetung_ct` | Einspeisevergütung in ct/kWh – Untergrenze des Preiskorridors | `8.0` |
| `preis_marge_ct` | Aufschlag in ct/kWh (gilt für Unter- und Obergrenze) | `6.0` |
| `preis_netzbezug_ct` | Netzbezugspreis in ct/kWh – Obergrenze des Preiskorridors | `30.0` |
| `preis_zielleistung_kw` | PV-Überschuss in kW, ab dem der günstigste Preis gilt | `11.0` |

Mit den Voreinstellungen liegt der Ladepreis zwischen **14 ct/kWh** (voller PV-Überschuss) und **36 ct/kWh** (Netzbezug).

### PV-Prognose

| Option | Bedeutung | Voreinstellung |
|---|---|---|
| `sensor_pv_morgen` | Erwarteter PV-Ertrag morgen in kWh | `sensor.morgenpv` |
| `sensor_pv_uebermorgen` | Erwarteter PV-Ertrag übermorgen in kWh | `sensor.uebermorgenpv` |
| `sensor_pv_in3tagen` | Erwarteter PV-Ertrag in 3 Tagen in kWh | `sensor.pvin3tagen` |
| `sensor_pv_erzeugung_heute` | Heutige PV-Erzeugung in % des Tagesziels | `sensor.prozentpverzeugungheute` |

### Fahrzeug & Ladestation

| Option | Bedeutung | Voreinstellung |
|---|---|---|
| `sensor_fahrzeug_akku` | Aktueller Ladestand des Fahrzeugs in % | `sensor.mein_fahrzeug_battery` |
| `sensor_ladegeraet_status` | Fahrzeugstatus am Ladegerät (`Charging`, `Complete`, …) | `sensor.go_echarger_XXXXXX_car` |
| `sensor_zaehlerstand_kwh` | Gesamtzähler der Wallbox in kWh (steigt monoton) | `sensor.go_echarger_XXXXXX_eto` |
| `sensor_kosten_integral` | Riemann-Integral der Ladekosten in € (steigt monoton) | `sensor.go_echarger_kosten_integral_2` |
| `sensor_rfid_karte` | Zuletzt erkannte RFID-Karte | `select.go_echarger_XXXXXX_trx` |

### evcc-Sensoren (optional)

Nur nötig, wenn evcc installiert ist. Leer lassen, wenn nicht vorhanden.

| Option | Bedeutung |
|---|---|
| `sensor_session_energie` | Energie der laufenden Session in kWh |
| `sensor_session_dauer` | Dauer der laufenden Session in Sekunden |
| `sensor_session_soc` | Fahrzeug-SOC laut evcc in % |

### Standardwerte & optionale HA-Entities

| Option | Bedeutung | Voreinstellung |
|---|---|---|
| `hausverbrauch_kwh` | Täglicher Hausverbrauch in kWh (für PV-Überschuss-Berechnung) | `10.0` |
| `ladeziel_soc` | Gewünschter Ziel-SOC des Fahrzeugs in % | `80` |
| `helper_hausverbrauch` | Optional: HA-Entity-ID, die den Standardwert überschreibt | `""` |
| `helper_ladeziel_soc` | Optional: HA-Entity-ID, die den Standardwert überschreibt | `""` |

### Ausgabe & Darstellung

| Option | Bedeutung | Voreinstellung |
|---|---|---|
| `qr_code_url` | URL als QR-Code auf dem E-Paper-Display | `https://nachbarschaft-laden.de/local/nachbarschaft-laden/index.html` |
| `web_unterverzeichnis` | Unterordner unter `/config/www/` für alle erzeugten Dateien | `nachbarschaft-laden` |

### RFID-Benutzer

Für jede Ladekarte einen Eintrag anlegen:

```yaml
rfid_benutzer:
  - rfid: "04AB12CD34EF56"
    name: "Max Mustermann"
    payment_helper: "input_number.nl_bezahlt_max_mustermann"
```

Das Add-on legt den unter `payment_helper` angegebenen `input_number`-Helper **automatisch** in HA an, falls er noch nicht existiert. Sobald dort ein Betrag eingetragen wird, wird er vom offenen Saldo abgezogen und der Helper auf 0 zurückgesetzt.

Die RFID-ID lässt sich ermitteln, indem die Karte ans Ladegerät gehalten und dann der Zustand von `sensor_rfid_karte` in HA abgelesen wird.

---

## Preisbildung

Der Ladepreis wird aus dem aktuellen **PV-Überschuss** berechnet:

```
PV-Überschuss = Wallbox-Leistung − Netzleistung − Batterieentladung
Überschussgrad = min(PV-Überschuss / Zielleistung, 1.0)

Preis = Netzbezugspreis + Marge − Überschussgrad × Preiskorridor
```

Mit den Standardwerten:

| Situation | Überschuss | Preis |
|---|---|---|
| Volles Netz, kein PV | 0 % | 36 ct/kWh |
| Halber PV-Überschuss | 50 % | 25 ct/kWh |
| Voller PV-Überschuss (≥ 11 kW) | 100 % | 14 ct/kWh |

Der Preis wird in Echtzeit berechnet und alle 5 Minuten in den Preisverlauf eingetragen.

---

## Erzeugte Dateien

Alle Dateien landen unter `/config/www/<web_unterverzeichnis>/`:

| Datei | Inhalt |
|---|---|
| `data.json` | Aktueller Preis, Preisverlauf, PV-Prognose, Ladevorgang-Status |
| `sessions.json` | Alle Ladesessions (max. 500) |
| `balances.json` | Offene Salden je Benutzer |
| `price_history.json` | Roher Preisverlauf (72 h) |
| `display_preview.png` | 480×800px Vorschau des E-Paper-Displays |

Zusätzlich wird `/config/www/display_combined.png` (460×160px, 1-bit) für das E-Paper-Display geschrieben.

---

## E-Paper-Display (optional)

Das Display (Waveshare 7,5") läuft via ESPHome auf einem ESP32:

1. `epaper/display.yaml` anpassen: unter `http_request → url` die HA-URL eintragen
2. Flashen:
   ```bash
   esphome compile epaper/display.yaml
   esphome upload epaper/display.yaml
   ```

Das Display lädt alle 60 Sekunden das aktuelle Bild von HA.

---

## Nachbarschaft-Laden (English)

[🇩🇪 Deutsch](#nachbarschaft-laden) · [🇬🇧 English](#nachbarschaft-laden-english)

Home Assistant add-on for managing a shared neighborhood EV charging station. It calculates a dynamic charging price based on current PV surplus, records charging sessions, and displays everything on a web dashboard and an e-paper display.

**[→ Live demo with sample data](https://bernd780.github.io/Nachbarschaft-Laden/)**

---

### Who is this for?

You have a solar PV system, a wallbox — and neighbors who'd love to charge at a fair price?

**Nachbarschaft-Laden** makes exactly that possible: the charging price drops automatically when the sun is shining. Each charging session is attributed to a user via RFID card and tracked for billing. No cloud service, no subscriptions — everything runs locally in Home Assistant.

---

### Features

- **Dynamic charging price** — calculated in real time from grid power, wallbox power, and battery discharge
- **Price history** — 72-hour log, smoothed into 15-minute buckets
- **PV forecast** — 3-day preview as a smiley scale (sad to very happy)
- **Session tracking** — energy, cost, duration, and user (via RFID) per charging session
- **Balance management** — open amounts per user, payments bookable via HA helpers
- **Web interface** — `index.html` (price dashboard) and `sessions.html` (session history)
- **E-paper display** — 460×160 smiley image for Waveshare 7.5" via ESPHome

---

### Installation

#### Requirements

- Home Assistant OS or Supervised
- go-eCharger with HA integration
- PV system with real-time power sensor

#### Install the add-on

1. Copy the `addon/` folder to the HA host, e.g. to `/addons/nachbarschaft-laden/`
2. In HA: **Settings → Add-ons → Add-on Store → ⋮ → Reload local add-ons**
3. Find "Nachbarschaft-Laden" under "Local add-ons" → **Install → Start**

---

### Configuration

After installation: **Add-on → Configuration**. All fields have sensible defaults.

#### Charging price calculation

The add-on calculates the price directly from three power sensors. No external price sensor required.

**Input sensors**

| Option | Description | Default |
|---|---|---|
| `sensor_netzleistung` | Grid power at main meter in W (positive = consumption, negative = feed-in) | `sensor.leistung_stromzaehler` |
| `sensor_wallbox_leistung` | Current wallbox charging power in W | `sensor.go_echarger_XXXXXX_nrg_12` |
| `sensor_batterie_leistung` | Current battery discharge power in W (positive = discharging) | `sensor.summe_battery_leistung` |

**Price constants**

| Option | Description | Default |
|---|---|---|
| `preis_einspeiseverguetung_ct` | Feed-in tariff in ct/kWh — lower bound of the price corridor | `8.0` |
| `preis_marge_ct` | Markup in ct/kWh (applied to both bounds) | `6.0` |
| `preis_netzbezug_ct` | Grid purchase price in ct/kWh — upper bound of the price corridor | `30.0` |
| `preis_zielleistung_kw` | PV surplus in kW at which the lowest price applies | `11.0` |

With the default settings, the charging price ranges between **14 ct/kWh** (full PV surplus) and **36 ct/kWh** (grid only).

#### PV forecast

| Option | Description | Default |
|---|---|---|
| `sensor_pv_morgen` | Expected PV yield tomorrow in kWh | `sensor.morgenpv` |
| `sensor_pv_uebermorgen` | Expected PV yield the day after tomorrow in kWh | `sensor.uebermorgenpv` |
| `sensor_pv_in3tagen` | Expected PV yield in 3 days in kWh | `sensor.pvin3tagen` |
| `sensor_pv_erzeugung_heute` | Today's PV generation as % of daily target | `sensor.prozentpverzeugungheute` |

#### Vehicle & charging station

| Option | Description | Default |
|---|---|---|
| `sensor_fahrzeug_akku` | Current vehicle battery level in % | `sensor.mein_fahrzeug_battery` |
| `sensor_ladegeraet_status` | Vehicle status at charger (`Charging`, `Complete`, …) | `sensor.go_echarger_XXXXXX_car` |
| `sensor_zaehlerstand_kwh` | Wallbox total energy counter in kWh (monotonically increasing) | `sensor.go_echarger_XXXXXX_eto` |
| `sensor_kosten_integral` | Riemann integral of charging costs in € (monotonically increasing) | `sensor.go_echarger_kosten_integral_2` |
| `sensor_rfid_karte` | Last detected RFID card | `select.go_echarger_XXXXXX_trx` |

#### RFID users

Add one entry per RFID card:

```yaml
rfid_benutzer:
  - rfid: "04AB12CD34EF56"
    name: "Jane Smith"
    payment_helper: "input_number.nl_paid_jane_smith"
```

The add-on automatically creates the `input_number` helper specified under `payment_helper` in HA if it does not yet exist. When an amount is entered there, it is deducted from the open balance and the helper is reset to 0.

To find the RFID ID, hold the card against the charger and then read the state of `sensor_rfid_karte` in HA.

---

### Price calculation

The charging price is derived from the current **PV surplus**:

```
PV surplus = wallbox power − grid power − battery discharge
Surplus ratio = min(PV surplus / target power, 1.0)

Price = grid price + margin − surplus ratio × price corridor
```

With default values:

| Situation | Surplus | Price |
|---|---|---|
| Full grid, no PV | 0 % | 36 ct/kWh |
| Half PV surplus | 50 % | 25 ct/kWh |
| Full PV surplus (≥ 11 kW) | 100 % | 14 ct/kWh |

The price is calculated in real time and recorded in the price history every 5 minutes.

---

### Generated files

All files are written to `/config/www/<web_unterverzeichnis>/`:

| File | Content |
|---|---|
| `data.json` | Current price, price history, PV forecast, session status |
| `sessions.json` | All charging sessions (max. 500) |
| `balances.json` | Open balances per user |
| `price_history.json` | Raw price history (72 h) |
| `display_preview.png` | 480×800px preview of the e-paper display |

Additionally, `/config/www/display_combined.png` (460×160px, 1-bit) is written for the e-paper display.

---

### E-paper display (optional)

The display (Waveshare 7.5") runs via ESPHome on an ESP32:

1. Edit `epaper/display.yaml`: enter the HA URL under `http_request → url`
2. Flash:
   ```bash
   esphome compile epaper/display.yaml
   esphome upload epaper/display.yaml
   ```

The display fetches the current image from HA every 60 seconds.
