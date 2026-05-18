# Nachbarschaft-Laden Add-on – Installationsanleitung

Dieses Add-on ersetzt den AppDaemon-Add-on und läuft als eigenständiger Docker-Container in Home Assistant. Es übernimmt Ladepreis-Visualisierung, Session-Tracking und E-Paper-Display-Generierung.

---

## Voraussetzungen

- Home Assistant OS oder Supervised
- Eine HA-Integration, die den aktuellen Strompreis liefert (z. B. **Ostrom**, **Tibber** oder **EPEX Spot**)
- go-eCharger mit HA-Integration (direkt oder via evcc)
- Optionale Hardware: Waveshare 7,5" E-Paper-Display via ESPHome

---

## 1. Add-on installieren

### Option A – Lokales Add-on (empfohlen zum Testen)

1. Den Ordner `addon/` aus diesem Repository auf den HA-Host kopieren, z. B. nach `/addons/nachbarschaft-laden/`
2. In HA: **Einstellungen → Add-ons → Add-on-Store → ⋮ → Lokale Add-ons neu laden**
3. Das Add-on „Nachbarschaft-Laden" erscheint unter „Lokale Add-ons" → **Installieren**

### Option B – Repository hinzufügen

1. In HA: **Einstellungen → Add-ons → Add-on-Store → ⋮ → Repositories**
2. URL des GitHub-Repositories eintragen (das Repo muss eine `repository.json` im Wurzelverzeichnis haben)
3. Add-on installieren

---

## 2. Hilfsfelder

**Keine HA-Helfer nötig.** Das Add-on verwaltet alle Zwischenwerte intern:

- Zählerstand und Kosten-Integral beim Session-Start werden in `session_active.json` gespeichert
- Hausverbrauch und Ladeziels-SOC sind feste Werte in der Add-on-Konfiguration

Optional können für Hausverbrauch und Ladeziels-SOC HA-Entities eingetragen werden – dann wird der dort eingestellte Wert live verwendet und kann über ein Dashboard geändert werden, ohne das Add-on neu zu starten.

---

## 3. Add-on konfigurieren

Nach der Installation: **Add-on → Konfiguration**. Alle Felder haben sinnvolle Voreinstellungen; anpassen was von der eigenen HA-Installation abweicht.

### Ladepreis-Berechnung

Das Add-on berechnet den dynamischen Ladepreis selbst, direkt aus Netzleistung, Wallbox-Leistung und Batterieentladung. Je größer der PV-Überschuss, desto günstiger der Preis – zwischen Einspeisevergütung+Marge (günstig) und Netzbezugspreis+Marge (teuer).

**Eingangssensoren:**

| Option | Bedeutung | Voreinstellung |
|--------|-----------|----------------|
| `sensor_netzleistung` | Aktuelle Netzleistung am Hauptzähler in W (positiv = Bezug, negativ = Einspeisung) | `sensor.leistung_stromzaehler` |
| `sensor_wallbox_leistung` | Aktuelle Ladeleistung der Wallbox in W | `sensor.go_echarger_XXXXXX_nrg_12` |
| `sensor_batterie_leistung` | Aktuelle Batterieleistung in W (positiv = Entladung) | `sensor.summe_battery_leistung` |

**Preiskonstanten:**

| Option | Bedeutung | Voreinstellung |
|--------|-----------|----------------|
| `preis_einspeiseverguetung_ct` | Einspeisevergütung in ct/kWh (Untergrenze des Preiskorridors) | `8.0` |
| `preis_marge_ct` | Aufschlag auf Ein- und Bezugspreis in ct/kWh | `6.0` |
| `preis_netzbezug_ct` | Netzbezugspreis in ct/kWh (Obergrenze des Preiskorridors) | `30.0` |
| `preis_zielleistung_kw` | PV-Überschuss in kW, ab dem der Mindestpreis gilt | `11.0` |

### PV-Prognose

| Option | Bedeutung | Beispiel |
|--------|-----------|---------|
| `sensor_pv_morgen` | Erwarteter PV-Ertrag morgen in kWh | `sensor.morgenpv` |
| `sensor_pv_uebermorgen` | Erwarteter PV-Ertrag übermorgen in kWh | `sensor.uebermorgenpv` |
| `sensor_pv_in3tagen` | Erwarteter PV-Ertrag in 3 Tagen in kWh | `sensor.pvin3tagen` |
| `sensor_pv_erzeugung_heute` | Heutige PV-Erzeugung in kWh (tatsächlich erzeugt) | `sensor.pv_erzeugung_heute` |

Der Prozentsatz (heute erzeugt / Tagesprognose) wird vom Add-on **selbst berechnet** aus `sensor_pv_erzeugung_heute` und den drei Prognose-Sensoren. Die Prognose-Sensoren lassen sich bei Bedarf überschreiben:

| Option | Bedeutung | Voreinstellung |
|--------|-----------|----------------|
| `sensor_pv_prognose_heute_1` | Tagesprognose Sensor 1 in kWh (Solcast) | `sensor.energy_production_today` |
| `sensor_pv_prognose_heute_2` | Tagesprognose Sensor 2 in kWh (Solcast) | `sensor.energy_production_today_2` |
| `sensor_pv_prognose_heute_3` | Tagesprognose Sensor 3 in kWh (Solcast) | `sensor.energy_production_today_3` |

### Fahrzeug & Ladestation (go-eCharger)

| Option | Bedeutung | Beispiel |
|--------|-----------|---------|
| `sensor_fahrzeug_akku` | Aktueller Akku-Ladestand des Fahrzeugs in % | `sensor.mein_fahrzeug_battery` |
| `sensor_ladegeraet_status` | Fahrzeugstatus am Ladegerät (`Charging`, `Complete`, …) | `sensor.go_echarger_XXXXXX_car` |
| `sensor_zaehlerstand_kwh` | Gesamter Zählerstand des Ladegeräts in kWh (steigt monoton) | `sensor.go_echarger_XXXXXX_eto` |
| `sensor_kosten_integral` | Riemann-Integral der Ladekosten in € (steigt monoton) | `sensor.go_echarger_kosten_integral_2` |
| `sensor_rfid_karte` | Zuletzt erkannte RFID-Karte | `select.go_echarger_XXXXXX_trx` |

### evcc-Sensoren (Session-Details)

| Option | Bedeutung | Beispiel |
|--------|-----------|---------|
| `sensor_session_energie` | Energie der laufenden Session in kWh (evcc) | `sensor.evcc_go_echarger_ocpp_session_energy` |
| `sensor_session_dauer` | Dauer der laufenden Session in Sekunden (evcc) | `sensor.evcc_go_echarger_ocpp_charge_duration` |
| `sensor_session_soc` | Fahrzeug-SOC laut evcc in % | `sensor.evcc_go_echarger_ocpp_vehicle_soc` |

### Standardwerte & optionale HA-Entities

| Option | Bedeutung | Voreinstellung |
|--------|-----------|----------------|
| `hausverbrauch_kwh` | Täglicher Hausverbrauch in kWh (Standardwert) | `10.0` |
| `ladeziel_soc` | Gewünschter Ziel-SOC des Fahrzeugs in % (Standardwert) | `80` |
| `helper_hausverbrauch` | Optional: HA-Entity-ID, überschreibt `hausverbrauch_kwh` live | `""` |
| `helper_ladeziel_soc` | Optional: HA-Entity-ID, überschreibt `ladeziel_soc` live | `""` |

### Ausgabe & Darstellung

| Option | Bedeutung | Voreinstellung |
|--------|-----------|----------------|
| `basis_url` | Basis-URL der HA-Instanz (ohne abschließenden `/`), ersetzt alle Links in den Web-Frontends | `https://nachbarschaft-laden.de` |
| `qr_code_url` | Vollständige URL für den QR-Code auf dem E-Paper-Display | `https://nachbarschaft-laden.de/local/nachbarschaft-laden/index.html` |
| `web_unterverzeichnis` | Unterordner unter `/config/www/` für alle generierten Dateien | `nachbarschaft-laden` |

> **Hinweis:** `basis_url` wirkt erst nach einem Add-on-Neustart, da die HTML-Dateien beim Start einmalig mit der konfigurierten URL generiert werden. Typische Werte: `https://meine-domain.de`, `http://homeassistant.local:8123` oder `http://192.168.1.10:8123`.

### RFID-Benutzer

Für jede Ladekarte einen Eintrag anlegen:

```yaml
rfid_benutzer:
  - rfid: "04AB12CD34EF56"     # RFID-ID der Karte (aus HA-Logs oder select-Entity auslesen)
    name: "Max Mustermann"      # Anzeigename in der Sessions-Übersicht
    payment_helper: "input_number.nl_bezahlt_max_mustermann"  # Hilfsentität für Zahlungsverbuchung
```

> **RFID-ID ermitteln:** Karte an das Ladegerät halten, dann in HA den Zustand von `sensor_rfid_karte` ablesen. Der Wert ist die Karten-ID.

> **Ohne RFID-Nutzer** funktioniert das Add-on vollständig – Sessions werden dann ohne Benutzerzuordnung gespeichert.

---

## 4. Extern in HA erforderliche Helfer

Zwei Sensoren müssen **einmalig in Home Assistant** angelegt werden. Das Add-on kann sie nicht selbst erzeugen, da sie HA-native Integrations-Typen nutzen (Template + Riemann-Summe).

### 4a. Template-Sensor `sensor.go_echarger_kosten_rate` (€/h)

Dieser Sensor berechnet die aktuelle Ladekostenrate aus Wallbox-Leistung und dem aktuellen Ladepreis.

**Über eine YAML-Paketdatei anlegen** (empfohlen):

Datei `/config/integrations/nachbarschaft_laden_kosten.yaml` anlegen:

```yaml
template:
  - sensor:
      - name: "go_echarger_kosten_rate"
        unique_id: "go_echarger_kosten_rate"
        unit_of_measurement: "€/h"
        state_class: measurement
        state: >
          {% set w = states('sensor.go_echarger_XXXXXX_nrg_12') | float(0) %}
          {% set ct = states('sensor.expgldurchschnitt_ema_asymalpha') | float(0) %}
          {{ ((w / 1000) * ct / 100) | round(6) }}
```

Sensor-IDs an die eigene Installation anpassen:
- `sensor.go_echarger_XXXXXX_nrg_12` → Wallbox-Leistung in W
- `sensor.expgldurchschnitt_ema_asymalpha` → aktueller Ladepreis in ct/kWh (aus dem Add-on oder einer Preisintegration)

Dann in `configuration.yaml` einbinden:
```yaml
homeassistant:
  packages: !include_dir_named integrations
```

**Alternativ per UI:** Einstellungen → Helfer → Erstellen → Template-Sensor, Formel wie oben eintragen.

### 4b. Riemann-Summen-Integral `sensor.go_echarger_kosten_integral` (€)

Dieser Sensor integriert `go_echarger_kosten_rate` über die Zeit und liefert die kumulierten Ladekosten in €.

**Per UI anlegen:**

1. **Einstellungen → Geräte & Dienste → Helfer → Erstellen → Riemann-Summen-Integral**
2. Felder ausfüllen:
   | Feld | Wert |
   |------|------|
   | Name | `go_echarger_kosten_integral` |
   | Eingangssensor | `sensor.go_echarger_kosten_rate` |
   | Methode | Trapezoidal |
   | Präzision | 4 |
   | Zeiteinheit | Stunden |
3. HA legt automatisch `sensor.go_echarger_kosten_integral` (oder `..._2` bei Namenskonflikt) an

Die generierte Entity-ID in der Add-on-Konfiguration unter `sensor_kosten_integral` eintragen.

> **Warum extern?** Das Integral muss über Neustarts und Session-Grenzen hinweg akkumulieren. HA's Riemann-Summe ist dafür zuverlässiger als eine selbstverwaltete JSON-Datei im Add-on.

---

## 5. Zahlungs-Helfer (optional)

Das Add-on legt für jeden konfigurierten RFID-Nutzer mit gesetztem `payment_helper` **automatisch** einen `input_number`-Helper in HA an. Manuelles Anlegen ist nicht nötig.

Sobald ein Betrag in den Helper eingetragen wird, zieht das Add-on ihn vom offenen Saldo des Nutzers ab und setzt den Helper auf 0 zurück.

Die Entity-ID für jeden Nutzer wird so vergeben: `input_number.nl_bezahlt_<name>` — oder frei wählbar über das Feld `payment_helper` in der RFID-Konfiguration.

---

## 6. Add-on starten und prüfen

1. Add-on starten
2. Im **Log**-Tab prüfen:
   - `LadepreisGraph gestartet` → Preisvisualisierung aktiv
   - `LadeSession gestartet` → Session-Tracking aktiv
   - `Display-Preview gespeichert` → Bild wurde generiert
3. In HA unter `http://<ha-ip>/local/nachbarschaft-laden/` sollten `data.json` und `display_preview.png` abrufbar sein

---

## 7. Web-Frontend einrichten

Die HTML-Seiten aus dem `www/`-Verzeichnis manuell auf den HA-Host kopieren (bis das Add-on sie selbst ausliefert):

```bash
scp www/* root@<ha-ip>:/config/www/nachbarschaft-laden/
```

Oder über das bestehende `deploy.ps1`:

```powershell
.\deploy.ps1
```

Aufruf im Browser: `http://<ha-ip>/local/nachbarschaft-laden/index.html`

---

## 8. Cloudflare-Domain einrichten (optional)

Wenn Home Assistant über eine eigene Domain erreichbar sein soll (z. B. `https://nachbarschaft-laden.de`), empfiehlt sich Cloudflare als DNS-Provider und Reverse-Proxy. Die folgenden Schritte setzen voraus, dass der HA-Host bereits über einen Cloudflare-Tunnel oder eine Port-Weiterleitung erreichbar ist.

### 8a. Redirect: Domain-Root → index.html

Damit `https://nachbarschaft-laden.de` direkt auf die App weiterleitet, statt einen leeren HA-Login zu zeigen:

**Cloudflare Dashboard → Domain → Rules → Redirect Rules → Create Rule**

| Feld | Wert |
|------|------|
| Rule-Name | `Root zu index.html` |
| Feld | `URI Path` |
| Operator | `equals` |
| Wert | `/` |
| Dann | **Static redirect** |
| Redirect-URL | `https://nachbarschaft-laden.de/local/nachbarschaft-laden/index.html` |
| Status-Code | `302` |

> Den Pfad `/local/nachbarschaft-laden/` dem Wert der Option `web_unterverzeichnis` anpassen.

---

### 8b. Redirect: www-Subdomain → Apex-Domain

Damit `https://www.nachbarschaft-laden.de` auf die Hauptdomain umleitet:

**Rules → Redirect Rules → Create Rule**

| Feld | Wert |
|------|------|
| Rule-Name | `www zu Apex` |
| Feld | `Hostname` |
| Operator | `equals` |
| Wert | `www.nachbarschaft-laden.de` |
| Dann | **Dynamic redirect** |
| Redirect-URL | `concat("https://nachbarschaft-laden.de", http.request.uri.path)` |
| Status-Code | `301` |

---

### 8c. Security Rule: Nur das konfigurierte Unterverzeichnis erlauben

Diese WAF-Regel blockiert alle Anfragen, die **nicht** das konfigurierte Unterverzeichnis im Pfad enthalten — schützt damit den HA-Login und alle anderen HA-Routen vor unberechtigtem Zugriff.

**Security → WAF → Custom Rules → Create Rule**

| Feld | Wert |
|------|------|
| Rule-Name | `Nur Ladestation-Pfad erlauben` |
| Feld | `URI Path` |
| Operator | `does not contain` |
| Wert | `/local/nachbarschaft-laden` |
| Dann | **Block** |

> Den Wert `/local/nachbarschaft-laden` dem Wert der Option `web_unterverzeichnis` anpassen: `/local/<web_unterverzeichnis>`.

**Wichtig:** Diese Regel blockiert auch den Cloudflare-Tunnel-Health-Check und ähnliche interne Anfragen — falls der Tunnel Probleme meldet, ggf. eine Ausnahme für `/cdn-cgi/` ergänzen:

Vollständige Bedingung:
```
(not http.request.uri.path contains "/local/nachbarschaft-laden") and
(not http.request.uri.path contains "/cdn-cgi/")
```

---

## 9. E-Paper-Display einrichten (optional)

Das Display (Waveshare 7,5") läuft via ESPHome auf einem ESP32.

1. `epaper/display.yaml` anpassen: unter `http_request → url` die HA-URL eintragen
2. Flashen:
   ```bash
   esphome compile epaper/display.yaml
   esphome upload epaper/display.yaml
   ```

Das Display holt alle 60 Sekunden das Bild `display_combined.png` von HA.

---

## Erzeugte Dateien

Alle Dateien landen unter `/config/www/<web_unterverzeichnis>/`:

| Datei | Inhalt |
|-------|--------|
| `data.json` | Aktueller Preis, Preisverlauf (72h), PV-Prognose, Ladevorgang-Status |
| `display_preview.png` | 480×800px-Vorschau des E-Paper-Displays |
| `sessions.json` | Alle Ladesessions (max. 500) |
| `balances.json` | Offene Salden je Benutzer |
| `price_history.json` | Roher Preisverlauf (intern, 72h) |

Zusätzlich wird `/config/www/display_combined.png` (460×160px, 1-bit) für das E-Paper-Display geschrieben.
