# Changelog

Alle relevanten Änderungen werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

## [1.0.3] – aktuell

### Hinzugefügt
- E-Paper Display: RSSI- und Uptime-Sensoren → Home Assistant
- E-Paper Display: Button „Sofort-Refresh" (lädt Bild neu + Full-Refresh)
- E-Paper Display: Nachtmodus 22–6 Uhr (nur alle 30 Minuten rendern)
- E-Paper Display: Pause-Modus via `input_boolean.nl_display_pause` + frei definierbarer Text
- E-Paper Display: Automatischer Zeilenumbruch im Pause-Text
- PV-Surplus-Werte als `input_number`-Helper (überleben HA-Neustart)
- HA-Überwachung: Automation bei Display offline/wieder online
- Beste Ladezeit: Forecast-Anzeige wenn heute noch keine Daten

### Behoben
- E-Paper: Falscher Preissensor (`expgldurchschnitt_ema_asymalpha` → `nl_ladepreis_aktuell`)
- E-Paper: Forecast-Werte lokal neu berechnet statt aus HA gelesen (unknown-Problem)
- index.html: Beste Ladezeit zeigt Forecast vor Kernzeit als Hauptbox
- `sensor_pv_peak_zeit_heute` war leer in apps.yaml → Forecast fehlte

### Geändert
- E-Paper: Full-Refresh-Intervall auf 10 Minuten erhöht (Displayschonung)
- E-Paper: Gleichmäßige Dritteilung des 800px-Screens
- E-Paper: Deutsche Sonderzeichen (ÄäÖöÜüß) in alle Fonts aufgenommen

## [1.0.2]

### Hinzugefügt
- Sessions-Seite: Optionaler Passwortschutz
- Preishistorie über 2 Wochen (price_history.json)
- display_preview.png als Spiegelung des E-Paper-Layouts

### Geändert
- Ladepreis-Berechnung: PV-Überschuss-basiert statt Spotmarkt
- AppDaemon: Atomares Schreiben aller JSON-Dateien (.tmp + os.replace)

## [1.0.1]

### Hinzugefügt
- E-Paper Display: Smiley-Prognose für 3 Tage
- Günstigste Ladezeit (Kernzeit-Auswertung)
- Vortags-Vergleich im Web-Dashboard

## [1.0.0]

### Erstveröffentlichung
- Dynamischer Ladepreis aus PV-Überschuss
- RFID-Session-Tracking via go-eCharger
- Web-Dashboard (index.html, sessions.html)
- AppDaemon-Apps: ladeSession.py, ladepreis_graph.py
