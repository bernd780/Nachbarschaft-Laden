import appdaemon.plugins.hass.hassapi as hass
import json
import os
from datetime import datetime, timezone

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
        self.WWW_DIR         = a.get("www_dir",                   "/homeassistant/www/nachbarschaft-laden")

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

        for entity_id in self.ZAHLUNGS_HELPERS.values():
            self.listen_state(self._on_payment_change, entity_id)
        self._init_balances()

        self.log(f"Überwache: {self.S_LADEGERAET}, RFID: {self.S_RFID}")

    def on_car_change(self, entity, attribute, old, new, kwargs):
        self.log(f"Ladegerät-Status: {old} → {new}")
        if new == "Charging" and not self._session_active:
            self._session_start_handler()
        elif new == "Charging" and self._session_active and self._end_timer:
            self.cancel_timer(self._end_timer)
            self._end_timer = None
            self.log("Schnelle Wiederverbindung – Session wird fortgesetzt")
        elif old == "Charging" and new != "Charging" and self._session_active:
            self._end_timer = self.run_in(self._session_end_handler, 10)

    def _session_start_handler(self):
        self._session_active = True
        self._session_start  = datetime.now(timezone.utc).isoformat()
        self._rfid_at_start  = self._get_rfid()
        self._price_samples  = []

        eto      = self._float(self.S_ZAEHLER)
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

        session = {
            "id":            end_time,
            "start":         self._session_start or end_time,
            "end":           end_time,
            "rfid":          rfid or "",
            "user":          user,
            "energy_kwh":    energy,
            "price_eur":     price_eur,
            "price_kwh":     price_kwh,
            "duration_s":    int(duration) if duration else 0,
            "soc_end":       round(soc, 0) if soc else None,
            "price_samples": self._price_samples,
        }

        self.log(
            f"Session gespeichert: {user} (RFID: {rfid or '–'}) | "
            f"{energy:.3f} kWh | {price_eur} € | "
            f"Ø {price_kwh*100:.1f} ct/kWh | {len(self._price_samples)} Preissamples"
            if price_kwh else
            f"Session gespeichert: {user} | {energy:.3f} kWh | {price_eur} €"
        )

        self._save_session(session)
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

    def _berechne_ladepreis(self):
        """Dynamischer Ladepreis basierend auf PV-Überschuss (ct/kWh)."""
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
