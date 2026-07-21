import appdaemon.plugins.hass.hassapi as hass
import json
import os
import glob
import zipfile
from datetime import datetime, timedelta, timezone

class LadeSession(hass.Hass):
    """
    Erfasst Ladesessions vom go-eCharger.
    Session-Start: sensor_ladegeraet_status → Charging
    Session-Ende:  sensor_ladegeraet_status von Charging → *
    Energie:       Zählerstand-Differenz (sensor_zaehlerstand_kwh)
    Kosten:        Kosten-Integral-Differenz (Riemann-Summe, exakt)
    """

    def initialize(self):
        self.log("LadeSession gestartet")

        a = self.args
        self.S_LADEGERAET    = a.get("sensor_ladegeraet_status",  "sensor.go_echarger_XXXXXX_car")
        self.S_ZAEHLER       = a.get("sensor_zaehlerstand_kwh",   "sensor.go_echarger_XXXXXX_eto")
        self.S_KOSTEN        = a.get("sensor_kosten_integral",    "sensor.go_echarger_kosten_integral_2")
        self.S_RFID          = a.get("sensor_rfid_karte",         "select.go_echarger_XXXXXX_trx")
        self.S_SESSION_SOC   = a.get("sensor_session_soc",        "") or None
        # Preisberechnung – Eingangssensoren
        self.S_NETZLEISTUNG      = a.get("sensor_netzleistung",          "sensor.leistung_stromzaehler")
        self.S_WALLBOX_LEISTUNG  = a.get("sensor_wallbox_leistung",      "sensor.go_echarger_XXXXXX_nrg_12")
        self.S_BATTERIE_LEISTUNG = a.get("sensor_batterie_leistung",     "sensor.summe_battery_leistung")
        # Preisberechnung – Konstanten (ct/kWh bzw. kW)
        self.PREIS_EINSPEISUNG   = float(a.get("preis_einspeiseverguetung_ct", 8.0))
        self.PREIS_MARGE         = float(a.get("preis_marge_ct",               6.0))
        self.PREIS_NETZBEZUG     = float(a.get("preis_netzbezug_ct",           30.0))
        self.PREIS_ZIELLEISTUNG  = float(a.get("preis_zielleistung_kw",        11.0))
        self.REFERENZPREIS_CT    = float(a.get("referenzpreis_ct",            29.0))
        self.S_EVCC_MODUS        = a.get("sensor_evcc_modus",               "") or None
        self.WWW_DIR         = a.get("www_dir",                   "/homeassistant/www/nachbarschaft-laden")
        self.PRIVATE_DIR     = "/homeassistant/nachbarschaft-laden-data"
        os.makedirs(self.PRIVATE_DIR, exist_ok=True)

        self.SESSION_FILE  = os.path.join(self.WWW_DIR, "sessions.json")
        self.STATE_FILE    = os.path.join(self.WWW_DIR, "session_active.json")
        self.BALANCES_FILE = os.path.join(self.WWW_DIR, "balances.json")

        # RFID-Mapping: {"KARTENID": "Name"}
        # apps.yaml liefert rfid_benutzer als Dict {rfid: name}
        rfid_raw = a.get("rfid_benutzer") or {}
        if isinstance(rfid_raw, dict):
            self.RFID_BENUTZER = rfid_raw
        else:
            self.RFID_BENUTZER = {e["rfid"]: e["name"]
                                  for e in rfid_raw
                                  if isinstance(e, dict) and "rfid" in e and "name" in e}

        # Zahlungs-Helpers: {"Name": "input_number.entity_id"}
        # apps.yaml liefert zahlungs_helpers als Dict {name: entity_id}
        helpers_raw = a.get("zahlungs_helpers") or {}
        if isinstance(helpers_raw, dict):
            self.ZAHLUNGS_HELPERS = helpers_raw
        else:
            self.ZAHLUNGS_HELPERS = {e["name"]: e["payment_helper"]
                                     for e in (a.get("rfid_benutzer") or [])
                                     if isinstance(e, dict) and e.get("payment_helper")}

        self._session_active = False
        self._session_start  = None
        self._rfid_at_start  = None
        self._price_samples  = []
        self._eto_start      = 0.0
        self._integral_start = 0.0
        self._price_listener = None
        self._end_timer      = None

        os.makedirs(self.WWW_DIR, exist_ok=True)
        if not os.path.exists(self.SESSION_FILE):
            with open(self.SESSION_FILE, "w") as f:
                json.dump([], f)

        if self._restore_state():
            self.log(
                f"Session wiederhergestellt: gestartet {self._session_start}, "
                f"RFID={self._rfid_at_start}, {len(self._price_samples)} Preissamples"
            )
            self._price_listener = self.listen_state(
                self._on_price_change, self.S_NETZLEISTUNG)

        self.listen_state(self.on_car_change, self.S_LADEGERAET)

        if self.S_EVCC_MODUS:
            self.listen_state(self._on_evcc_mode_change, self.S_EVCC_MODUS)

        for entity_id in self.ZAHLUNGS_HELPERS.values():
            self.listen_state(self._on_payment_change, entity_id)
        self._init_balances()

        self.log(f"Überwache: {self.S_LADEGERAET}, RFID: {self.S_RFID}")

        # Ladestatus und Zähler-Lücken beim Start prüfen (verzögert, damit
        # HASS-Verbindung stabil ist)
        self.run_in(self._check_charging_at_startup, 5)
        self.run_in(self._check_gap_on_startup,      12)
        self.run_in(self._check_sensors,              8)

        # Backup: täglich 03:30, zusätzlich per Button-Helfer auslösbar.
        # Restore: ZIP in <PRIVATE_DIR>/restore/ legen, wird beim Start eingespielt.
        self.run_daily(self._backup_daily, "03:30:00")
        try:
            self.listen_state(self._on_backup_button, "input_button.nl_backup_erstellen")
        except Exception:
            pass
        self.run_in(self._check_restore, 3)

    def _check_sensors(self, kwargs):
        sensors = {
            "Ladegerät-Status":    self.S_LADEGERAET,
            "Zählerstand":         self.S_ZAEHLER,
            "Kosten-Integral":     self.S_KOSTEN,
            "RFID-Karte":          self.S_RFID,
            "Netzleistung":        self.S_NETZLEISTUNG,
            "Wallbox-Leistung":    self.S_WALLBOX_LEISTUNG,
            "Batterie-Leistung":   self.S_BATTERIE_LEISTUNG,
        }
        if self.S_SESSION_SOC:
            sensors["Session-SOC"] = self.S_SESSION_SOC
        if self.S_EVCC_MODUS:
            sensors["evcc-Modus"] = self.S_EVCC_MODUS

        warnings = []
        for label, entity_id in sensors.items():
            state = self.get_state(entity_id)
            if state is None:
                warnings.append({"sensor": entity_id, "label": label, "problem": "nicht gefunden"})
                self.log(f"Sensor nicht gefunden: {label} ({entity_id})", level="WARNING")
            elif state in ("unavailable", "unknown"):
                warnings.append({"sensor": entity_id, "label": label, "problem": state})
                self.log(f"Sensor {state}: {label} ({entity_id})", level="WARNING")

        status_path = os.path.join(self.WWW_DIR, "sensor_status.json")
        try:
            existing = {}
            if os.path.exists(status_path):
                with open(status_path) as f:
                    existing = json.load(f)
            existing["ladeSession"] = {
                "checked": datetime.now(timezone.utc).isoformat(),
                "warnings": warnings,
            }
            tmp = status_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            os.replace(tmp, status_path)
        except Exception as e:
            self.log(f"sensor_status.json schreiben fehlgeschlagen: {e}", level="WARNING")

        if not warnings:
            self.log("Alle Sensoren verfügbar")

    def _on_evcc_mode_change(self, entity, attribute, old, new, kwargs):
        if not self._session_active:
            return
        if old in (None, "unavailable", "unknown") or new in (None, "unavailable", "unknown"):
            return
        old_pv = old.lower() in ("pv", "minpv", "min+pv")
        new_pv = new.lower() in ("pv", "minpv", "min+pv")
        if old_pv == new_pv:
            return
        self.log(
            f"evcc-Modus gewechselt: {old} → {new} – "
            f"beende laufende Session und starte neue"
        )
        if self._end_timer:
            self.cancel_timer(self._end_timer)
            self._end_timer = None
        self._session_end_handler({})
        self._session_start_handler()

    def on_car_change(self, entity, attribute, old, new, kwargs):
        self.log(f"Ladegerät-Status: {old} → {new}")
        old_l = (old or "").lower()
        new_l = (new or "").lower()
        if new_l == "charging" and not self._session_active:
            self._session_start_handler()
        elif new_l == "charging" and self._session_active and self._end_timer:
            self.cancel_timer(self._end_timer)
            self._end_timer = None
            self.log("Schnelle Wiederverbindung – Session wird fortgesetzt")
        elif old_l == "charging" and new_l != "charging" and self._session_active:
            self._end_timer = self.run_in(self._session_end_handler, 10)

    def _session_start_handler(self):
        # Zählerstand VOR Session-Start lesen und auf Lücke prüfen
        eto      = self._float(self.S_ZAEHLER)
        self._check_gap_before_start(eto)

        self._session_active = True
        self._session_start  = datetime.now(timezone.utc).isoformat()
        self._rfid_at_start  = self._get_rfid()
        self._price_samples  = []

        integral = self._float(self.S_KOSTEN)
        self._eto_start      = eto
        self._integral_start = integral

        v = self._berechne_ladepreis()
        self._price_samples.append({
            "t": self._session_start,
            "v": round(v, 1)
        })

        self._price_listener = self.listen_state(
            self._on_price_change, self.S_NETZLEISTUNG)

        self._save_state()

        user = self._rfid_to_user(self._rfid_at_start) if self._rfid_at_start else "–"
        self.log(f"Session gestartet: RFID={self._rfid_at_start} ({user}) um {self._session_start}")

    def _on_price_change(self, entity, attribute, old, new, kwargs):
        if self._session_active and new not in (None, "unknown", "unavailable"):
            try:
                self._price_samples.append({
                    "t": datetime.now(timezone.utc).isoformat(),
                    "v": round(self._berechne_ladepreis(), 1)
                })
                self._save_state()
            except Exception:
                pass

    def _session_end_handler(self, kwargs):
        if not self._session_active:
            return
        self._session_active = False
        self._end_timer = None

        if self._price_listener:
            self.cancel_listen_state(self._price_listener)
            self._price_listener = None

        v = self._berechne_ladepreis()
        self._price_samples.append({
            "t": datetime.now(timezone.utc).isoformat(),
            "v": round(v, 1)
        })

        rfid = self._rfid_at_start or self._get_rfid()

        eto       = self._float(self.S_ZAEHLER)
        eto_start = self._eto_start
        energy    = round(eto - eto_start, 3) if eto > eto_start else 0.0

        if energy < 0.1:
            self.log(f"Session ignoriert (nur {energy:.3f} kWh)")
            self._reset()
            return

        end_time  = datetime.now(timezone.utc)
        start_dt  = datetime.fromisoformat(self._session_start)
        duration  = int((end_time - start_dt).total_seconds())
        soc       = self._float(self.S_SESSION_SOC) if self.S_SESSION_SOC else 0.0
        end_time  = end_time.isoformat()

        integral_now   = self._float(self.S_KOSTEN)
        integral_start = self._integral_start
        kosten_raw = integral_now - integral_start if integral_now > integral_start else 0.0
        kosten_session = round(kosten_raw, 4)
        if kosten_session > 0:
            price_eur = round(kosten_raw, 2)
            price_kwh = round(kosten_raw / energy, 4) if energy else None
        else:
            avg_price = (sum(s["v"] for s in self._price_samples) / len(self._price_samples)
                         if self._price_samples else self._berechne_ladepreis())
            price_eur = round(energy * avg_price / 100, 2) if avg_price else None
            price_kwh = round(avg_price / 100, 4) if avg_price else None

        user = self._rfid_to_user(rfid) if rfid else "–"

        ref_kwh = round(self.REFERENZPREIS_CT / 100, 4)
        savings = round((ref_kwh - price_kwh) * energy, 2) if price_kwh is not None else None

        session = {
            "id":            end_time,
            "start":         self._session_start or end_time,
            "end":           end_time,
            "rfid":          rfid or "",
            "user":          user,
            "energy_kwh":    energy,
            "price_eur":     price_eur,
            "price_kwh":     price_kwh,
            "ref_price_kwh": ref_kwh,
            "savings_eur":   savings,
            "evcc_modus":    (self.get_state(self.S_EVCC_MODUS) or "").lower() if self.S_EVCC_MODUS else None,
            "duration_s":    int(duration) if duration else 0,
            "soc_end":       round(soc, 0) if soc else None,
            "price_samples": self._price_samples,
            "eto_end":       eto,
        }

        self.log(
            f"Session gespeichert: {user} (RFID: {rfid or '–'}) | "
            f"{energy:.3f} kWh | {price_eur} € | "
            f"Ø {price_kwh*100:.1f} ct/kWh | {len(self._price_samples)} Preissamples"
            if price_kwh else
            f"Session gespeichert: {user} | {energy:.3f} kWh | {price_eur} €"
        )

        self._save_session(session)
        self._append_statistics(session)
        if price_eur and user in self.ZAHLUNGS_HELPERS:
            self._add_to_balance(user, price_eur)
        self._reset()

    def _reset(self):
        self._session_start  = None
        self._rfid_at_start  = None
        self._price_samples  = []
        self._eto_start      = 0.0
        self._integral_start = 0.0
        self._clear_state()

    # ── Lücken-Erkennung ────────────────────────────────────────────────────────

    def _check_charging_at_startup(self, kwargs):
        """Klärt beim Start den tatsächlichen Ladestatus.

        Fälle:
          Session aktiv (restore) + Fahrzeug lädt nicht mehr → beenden
          Keine Session aktiv + Fahrzeug lädt bereits → nachträglich starten
        """
        state = (self.get_state(self.S_LADEGERAET) or "").lower()
        if self._session_active and state != "charging":
            self.log(
                "Wiederhergestellte Session: Fahrzeug lädt nicht mehr – "
                "beende Session nach Neustart"
            )
            self._session_end_handler({})
        elif not self._session_active and state == "charging":
            self.log(
                "Fahrzeug lädt bereits beim Start – "
                "Session wird nachträglich gestartet"
            )
            self._session_start_handler()

    def _check_gap_on_startup(self, kwargs):
        """Prüft beim Start ob seit der letzten erfassten Session
        Energie am Zähler gelaufen ist, ohne dass eine Session
        aufgezeichnet wurde (z.B. wegen Add-on-Neustart)."""
        if self._session_active:
            return  # läuft bereits, kein Startup-Gap nötig
        last_eto = self._get_last_eto_end()
        if last_eto is None:
            return  # keine Referenz vorhanden
        current_eto = self._float(self.S_ZAEHLER)
        if current_eto < last_eto:
            self.log(
                f"Zähler-Reset erkannt ({last_eto:.1f} → {current_eto:.1f}) "
                "– kein Lücken-Eintrag"
            )
            return
        gap = round(current_eto - last_eto, 3)
        if gap >= 0.1:
            self._insert_gap(last_eto, current_eto, gap, "startup")

    def _check_gap_before_start(self, new_eto_start):
        """Prüft ob zwischen dem Ende der letzten Session und
        dem aktuellen Ladestart Energie unerfasst blieb."""
        last_eto = self._get_last_eto_end()
        if last_eto is None:
            return
        if new_eto_start < last_eto:
            self.log(
                f"Zähler-Reset erkannt ({last_eto:.1f} → {new_eto_start:.1f}) "
                "– kein Lücken-Eintrag"
            )
            return
        gap = round(new_eto_start - last_eto, 3)
        if gap >= 0.1:
            self._insert_gap(last_eto, new_eto_start, gap, "vor_session")

    def _get_last_eto_end(self):
        """Liefert den letzten bekannten absoluten Zählerstand aus
        sessions.json (aus regulären Sessions oder Lücken-Einträgen)."""
        try:
            if not os.path.exists(self.SESSION_FILE):
                return None
            with open(self.SESSION_FILE) as f:
                sessions = json.load(f)
            for s in reversed(sessions):
                if s.get("eto_end") is not None:
                    return float(s["eto_end"])
                if s.get("eto_gap_end") is not None:
                    return float(s["eto_gap_end"])
        except Exception as e:
            self.log(f"_get_last_eto_end fehlgeschlagen: {e}", level="WARNING")
        return None

    def _insert_gap(self, eto_start, eto_end, gap_kwh, reason="unknown"):
        """Fügt einen Lücken-Eintrag in sessions.json ein.
        Duplikate (gleicher Zählerbereich) werden übersprungen."""
        # Duplikat-Prüfung
        try:
            if os.path.exists(self.SESSION_FILE):
                with open(self.SESSION_FILE) as f:
                    sessions = json.load(f)
                for s in sessions:
                    if (s.get("type") == "lucke"
                            and abs(s.get("eto_gap_start", 0) - eto_start) < 0.05
                            and abs(s.get("eto_gap_end",   0) - eto_end)   < 0.05):
                        self.log("Lücken-Eintrag bereits vorhanden – übersprungen")
                        return
        except Exception:
            pass

        now = datetime.now(timezone.utc).isoformat()
        gap_entry = {
            "id":            "lucke-" + now,
            "type":          "lucke",
            "start":         now,
            "end":           now,
            "energy_kwh":    gap_kwh,
            "eto_gap_start": round(eto_start, 3),
            "eto_gap_end":   round(eto_end,   3),
            "user":          "–",
            "rfid":          "",
            "price_eur":     None,
            "price_kwh":     None,
            "duration_s":    0,
            "price_samples": [],
            "note":          "Nicht erfasst – Zähler-Lücke erkannt",
        }
        self._save_session(gap_entry)
        self.log(
            f"Lücken-Eintrag: {gap_kwh:.3f} kWh "
            f"(Zähler {eto_start:.1f} → {eto_end:.1f}, Grund: {reason})"
        )

    # ── Ende Lücken-Erkennung ────────────────────────────────────────────────

    def _get_rfid(self):
        try:
            state = self.get_state(self.S_RFID)
            if state in (None, "unknown", "unavailable", "", "none", "None"):
                return None
            return str(state).strip()
        except Exception as e:
            self.log(f"RFID auslesen fehlgeschlagen: {e}", level="WARNING")
            return None

    def _rfid_to_user(self, rfid):
        return self.RFID_BENUTZER.get(rfid, rfid)

    def _ist_ueberschussladen(self):
        if not self.S_EVCC_MODUS:
            return False
        modus = (self.get_state(self.S_EVCC_MODUS) or "").lower()
        return modus in ("pv", "minpv", "min+pv")

    def _berechne_ladepreis(self):
        """Dynamischer Ladepreis basierend auf PV-Überschuss (ct/kWh)."""
        if self._ist_ueberschussladen():
            return round(self.PREIS_EINSPEISUNG, 2)

        zaehler_w = self._float_safe(self.S_NETZLEISTUNG)
        wallbox_w = self._float_safe(self.S_WALLBOX_LEISTUNG)
        akku_w    = self._float_safe(self.S_BATTERIE_LEISTUNG)

        akku_entladung_w = max(akku_w, 0.0)
        ueberschuss_w    = wallbox_w - zaehler_w - akku_entladung_w
        ueberschuss_kw   = max(ueberschuss_w, 0.0) / 1000.0
        ueberschuss      = min(ueberschuss_kw / self.PREIS_ZIELLEISTUNG, 1.0)

        preis_min = self.PREIS_EINSPEISUNG + self.PREIS_MARGE
        preis_max = self.PREIS_NETZBEZUG   + self.PREIS_MARGE
        preis     = preis_max - ueberschuss * (preis_max - preis_min)
        return round(max(preis_min, min(preis_max, preis)), 2)

    def _float_safe(self, entity_id, default=0.0):
        try:
            v = self.get_state(entity_id)
            if v in (None, "unknown", "unavailable"):
                return default
            return float(v)
        except Exception:
            return default

    def _float(self, entity_id):
        try:
            val = self.get_state(entity_id)
            if val in (None, "unknown", "unavailable"):
                return 0.0
            return float(val)
        except Exception:
            return 0.0

    def _save_state(self):
        state = {
            "active":        self._session_active,
            "session_start": self._session_start,
            "rfid_at_start": self._rfid_at_start,
            "price_samples": self._price_samples,
            "eto_start":     self._eto_start,
            "integral_start": self._integral_start,
        }
        tmp = self.STATE_FILE + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(state, f, ensure_ascii=False)
            os.replace(tmp, self.STATE_FILE)
        except Exception as e:
            self.log(f"Zustand speichern fehlgeschlagen: {e}", level="WARNING")

    def _restore_state(self):
        if not os.path.exists(self.STATE_FILE):
            return False
        try:
            with open(self.STATE_FILE) as f:
                state = json.load(f)
            if not state.get("active"):
                return False
            self._session_active = True
            self._session_start  = state.get("session_start")
            self._rfid_at_start  = state.get("rfid_at_start")
            self._price_samples  = state.get("price_samples", [])
            self._eto_start      = float(state.get("eto_start", 0.0))
            self._integral_start = float(state.get("integral_start", 0.0))
            return True
        except Exception as e:
            self.log(f"Zustand wiederherstellen fehlgeschlagen: {e}", level="WARNING")
            return False

    def _clear_state(self):
        try:
            if os.path.exists(self.STATE_FILE):
                os.remove(self.STATE_FILE)
        except Exception as e:
            self.log(f"Zustandsdatei löschen fehlgeschlagen: {e}", level="WARNING")

    def _on_payment_change(self, entity, attribute, old, new, kwargs):
        if old in (None, "unavailable", "unknown") or old == new:
            return
        try:
            amount = float(new) if new not in (None, "unknown", "unavailable") else 0.0
        except Exception:
            return
        if amount <= 0:
            return
        user = next((u for u, eid in self.ZAHLUNGS_HELPERS.items() if eid == entity), None)
        if not user:
            return
        balances = self._load_balances()
        balances[user] = round(max(0.0, balances.get(user, 0.0) - amount), 2)
        self._save_balances(balances)
        try:
            self.call_service("input_number/set_value", entity_id=entity, value=0)
        except Exception as e:
            self.log(f"Helper zurücksetzen fehlgeschlagen: {e}", level="WARNING")
        self.log(f"Zahlung {amount:.2f} € für {user} verbucht, neuer offener Betrag: {balances[user]:.2f} €")

    def _init_balances(self):
        if os.path.exists(self.BALANCES_FILE):
            return
        balances = {user: 0.0 for user in self.ZAHLUNGS_HELPERS}
        self._save_balances(balances)

    def _add_to_balance(self, user, amount):
        balances = self._load_balances()
        balances[user] = round(balances.get(user, 0.0) + amount, 2)
        self._save_balances(balances)

    def _load_balances(self):
        try:
            if os.path.exists(self.BALANCES_FILE):
                with open(self.BALANCES_FILE) as f:
                    return json.load(f)
        except Exception as e:
            self.log(f"balances.json lesen fehlgeschlagen: {e}", level="WARNING")
        return {}

    def _save_balances(self, balances):
        tmp = self.BALANCES_FILE + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(balances, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.BALANCES_FILE)
        except Exception as e:
            self.log(f"balances.json schreiben fehlgeschlagen: {e}", level="WARNING")

    def _save_session(self, session):
        sessions = []
        try:
            if os.path.exists(self.SESSION_FILE):
                with open(self.SESSION_FILE) as f:
                    sessions = json.load(f)
        except Exception as e:
            self.log(f"Sessions-Datei lesen fehlgeschlagen: {e}", level="WARNING")

        sessions.append(session)

        if len(sessions) > 500:
            sessions = sessions[-500:]

        tmp = self.SESSION_FILE + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(sessions, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.SESSION_FILE)
            self.log(f"Sessions gespeichert: {len(sessions)} total")
        except Exception as e:
            self.log(f"Sessions speichern fehlgeschlagen: {e}", level="ERROR")

    # ── Long-Term Statistics ─────────────────────────────────────────────────

    STATS_MAX_DAYS = 365

    def _append_statistics(self, session):
        """Hängt eine abgeschlossene Session als Zeile an statistics.jsonl an.

        Format: eine JSON-Zeile pro Ereignis, maschinenlesbar für
        Grafana (Infinity Plugin), InfluxDB-Import, Pandas, etc.
        """
        stats_path = os.path.join(self.PRIVATE_DIR, "statistics.jsonl")
        try:
            duration_min = round(session.get("duration_s", 0) / 60, 1)
            entry = {
                "ts":           session.get("end") or session.get("start"),
                "ts_start":     session.get("start"),
                "typ":          "session",
                "benutzer":     session.get("user", "–"),
                "energie_kwh":  session.get("energy_kwh"),
                "preis_eur":    session.get("price_eur"),
                "preis_kwh":    round(session["price_kwh"] * 100, 2) if session.get("price_kwh") else None,
                "ersparnis_eur": session.get("savings_eur"),
                "evcc_modus":   session.get("evcc_modus"),
                "dauer_min":    duration_min,
                "soc_end":      session.get("soc_end"),
                "lucke":        session.get("type") == "lucke",
            }
            with open(stats_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._trim_statistics(stats_path)
        except Exception as e:
            self.log(f"Statistics schreiben fehlgeschlagen: {e}", level="WARNING")

    def _trim_statistics(self, path):
        """Entfernt Einträge die älter als STATS_MAX_DAYS sind."""
        try:
            cutoff = (datetime.now(timezone.utc)
                      - timedelta(days=self.STATS_MAX_DAYS)).isoformat()
            lines = []
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ts = json.loads(line).get("ts", "")
                        if ts >= cutoff:
                            lines.append(line)
                    except Exception:
                        pass
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n" if lines else "")
        except Exception:
            pass

    # ── Backup & Restore ─────────────────────────────────────────────────────

    BACKUP_KEEP = 10

    def _backup_files(self):
        """Alle Datendateien des Add-ons (Pfad, Name-im-ZIP)."""
        www = [("sessions.json", self.WWW_DIR), ("balances.json", self.WWW_DIR),
               ("price_history.json", self.WWW_DIR), ("data.json", self.WWW_DIR),
               ("session_active.json", self.WWW_DIR)]
        priv = [("statistics.jsonl", self.PRIVATE_DIR),
                ("health_history.json", self.PRIVATE_DIR)]
        return www + priv

    def _backup_daily(self, kwargs):
        self._create_backup(trigger="taeglich")

    def _on_backup_button(self, entity, attribute, old, new, kwargs):
        if new in (None, "unknown", "unavailable"):
            return
        self._create_backup(trigger="button")

    def _create_backup(self, trigger=""):
        backup_dir = os.path.join(self.PRIVATE_DIR, "backups")
        try:
            os.makedirs(backup_dir, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            zpath = os.path.join(backup_dir, f"nl_backup_{stamp}.zip")
            count = 0
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
                for name, folder in self._backup_files():
                    src = os.path.join(folder, name)
                    if os.path.exists(src):
                        z.write(src, name)
                        count += 1
            self.log(f"Backup erstellt ({trigger}): {zpath} ({count} Dateien)")
            # Nur die neuesten BACKUP_KEEP behalten
            backups = sorted(glob.glob(os.path.join(backup_dir, "nl_backup_*.zip")))
            for old_zip in backups[:-self.BACKUP_KEEP]:
                os.remove(old_zip)
        except Exception as e:
            self.log(f"Backup fehlgeschlagen: {e}", level="ERROR")

    def _check_restore(self, kwargs):
        """Spielt ein ZIP aus <PRIVATE_DIR>/restore/ ein (beim App-Start).

        Ablauf für Admins: ZIP dorthin kopieren, Add-on neu starten.
        Vor dem Einspielen wird ein Sicherungs-Backup des Ist-Zustands erstellt.
        Nach Erfolg wird das ZIP in .restored umbenannt.
        """
        restore_dir = os.path.join(self.PRIVATE_DIR, "restore")
        try:
            zips = sorted(glob.glob(os.path.join(restore_dir, "*.zip")))
        except Exception:
            return
        if not zips:
            return
        zpath = zips[0]
        self.log(f"Restore gefunden: {zpath}")
        self._create_backup(trigger="vor-restore")
        try:
            with zipfile.ZipFile(zpath) as z:
                names = set(z.namelist())
                targets = {n: d for n, d in self._backup_files() if n in names}
                if not targets:
                    self.log("Restore-ZIP enthält keine bekannten Dateien", level="ERROR")
                    return
                for name, folder in targets.items():
                    data = z.read(name)
                    # Validierung: muss parsbares JSON bzw. JSONL sein
                    text = data.decode("utf-8")
                    if name.endswith(".jsonl"):
                        for line in text.splitlines():
                            if line.strip():
                                json.loads(line)
                    else:
                        json.loads(text)
                    dst = os.path.join(folder, name)
                    tmp = dst + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        f.write(text)
                    os.replace(tmp, dst)
                    self.log(f"Restore: {name} → {folder}")
            os.replace(zpath, zpath + ".restored")
            self.log(f"Restore abgeschlossen: {len(targets)} Dateien. "
                     "Add-on ggf. erneut neu starten, damit alle Apps die Daten laden.")
        except Exception as e:
            self.log(f"Restore fehlgeschlagen (nichts überschrieben ab Fehlerdatei): {e}",
                     level="ERROR")
