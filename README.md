# Nachbarschaft-Laden

Home Assistant Add-on für die Verwaltung einer nachbarschaftlichen EV-Ladestation. Es berechnet einen dynamischen Ladepreis aus dem aktuellen PV-Überschuss, zeichnet Ladesessions auf und zeigt alles auf einer Webseite und einem E-Paper-Display an.

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
  <img src="docs/mockup_epaper.png" width="360" alt="E-Paper-Display Vorschau"/>
</p>

- **😄 Sehr glücklich** = voller PV-Überschuss, günstigster Preis
- **🙂 Glücklich** = guter Überschuss
- **😐 Neutral** = gemischte Bedingungen
- **😞 Traurig** = wenig PV, hoher Netzanteil

Das Display aktualisiert sich alle 60 Sekunden automatisch. Es läuft auf einem ESP32 via ESPHome und benötigt keinen eigenen Server.

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
