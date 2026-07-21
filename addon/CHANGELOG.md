# Changelog

## 1.0.6

- Fix: akku_soc_voll im Konfigurations-Schema war fälschlich als String typisiert (str statt int) – blockierte das Speichern der Add-on-Konfiguration
- Backup & Restore: tägliches Daten-Backup + manueller Button-Trigger, Restore per ZIP-Ordner
- Statistics-Logging (statistics.jsonl) + Health-History für KI-Anomalie-Erkennung, in nicht-öffentlichem Verzeichnis

## 1.0.5

- Ersparnis-Tracking: Ersparnis pro Session (ref. Hausstrom-Tarif), Gesamtersparnis im Header
- evcc-Modus: PV/MinPV-Laden wird erkannt → Einspeisevergütung als Ladepreis, ☀-Badge in Session-Liste
- Session-Split bei Moduswechsel zwischen PV und Normalladen
- Sensor-Verfügbarkeitsprüfung: Warnungen im Add-on-Log und im Web-Dashboard
- Sessions-Liste: mobile Ansicht identisch mit Desktop, alle 8 Spalten sichtbar
- Lücken-Erkennung: Uhrzeit immer sichtbar, Dauer erst nach Nachtragen
- Display-Vorschau: reaktiv aus HA-Helper-Werten gerendert (immer synchron mit E-Paper)
- Fix: go-eCharger Statuswerte (lowercase) korrekt erkannt → Sessions werden wieder erfasst
- Fix: render_combined Signatur für listen_state-Callback korrigiert
- Fix: sensor_kosten_integral ohne _2-Suffix (korrekter Sensor-Name)

## 1.0.3

- Startseite: Ersparnis-Rechner-Karte optisch unauffälliger
- Fix: display_combined.png wird im korrekten Modulpfad gespeichert
- Beispiel-Benutzer (Max Mustermann) in Konfiguration und sessions.json voreingestellt
- Fix: ladepreis_max/min dynamisch aus Konfiguration, nicht mehr hardcodiert
- MIT-Lizenz hinzugefügt

## 1.0.2

- Sessions-Seite: Passwortschutz-Option
- Web-Frontend: Robots-Meta-Tags und robots.txt für vollständige Crawler-Sperrung
- README: Foto des echten E-Paper-Displays, Erklärung der Display-Bereiche

## 1.0.1

- Sessions-Passwort in Add-on-Konfiguration

## 1.0.0

- Initial release
