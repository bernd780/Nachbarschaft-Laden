import appdaemon.plugins.hass.hassapi as hass
import json
import os
from datetime import datetime, timezone

class LadeSession(hass.Hass):
    """
    Erfasst Ladesessions vom go-eCharger.
    Session-Start: sensor.go_echarger_XXXXXX_car → Charging
    Session-Ende:  sensor.go_echarger_XXXXXX_car von Charging → *
    Energie:       ETO-Differenz (go_echarger_XXXXXX_eto - eto_start)
    Kosten:        sensor.go_echarger_kosten_session (Riemann-Summe, exakt)
    """

    SESSION_FILE      = "/homeassistant/www/nachbarschaft-laden/sessions.json"
    STATE_FILE        = "/homeassistant/www/nachbarschaft-laden/session_active.json"
    BALANCES_FILE     = "/homeassistant/www/nachbarschaft-laden/balances.json"

    # Benutzername → HA input_number entity_id für Zahlungseingabe
    PAYMENT_HELPERS = {
        "Anna Beispiel":   "input_number.nl_bezahlt_anna_beispiel",
        "Card 0":          "input_number.nl_bezahlt_card_0",
        "Klaus Weber":     "input_number.nl_bezahlt_klaus_weber",
        "Max Mustermann":  "input_number.nl_bezahlt_max_mustermann",
    }

    S_CAR       = "sensor.go_echarger_XXXXXX_car"
    S_ETO       = "sensor.go_echarger_XXXXXX_eto"
    S_ETO_START = "input_number.go_echarger_session_eto_start"
    S_KOSTEN_INTEGRAL       = "sensor.go_echarger_kosten_integral_2"
    S_KOSTEN_INTEGRAL_START = "input_number.go_echarger_kosten_integral_start"
    S_SOC       = "sensor.evcc_go_echarger_ocpp_vehicle_soc"
    S_PRICE_KWH = "sensor.expgldurchschnitt_ema_asymalpha"
    S_RFID      = "select.go_echarger_XXXXXX_trx"

    RFID_USERS = {
        # "KARTENID": "Benutzername",
    }

    def initialize(self):
        self.log("LadeSession gestartet")
        self._session_active = False
        self._session_start  = None
        self._rfid_at_start  = None
        self._price_samples  = []
        self._price_listener = None
        self._end_timer      = None

        os.makedirs(os.path.dirname(self.SESSION_FILE), exist_ok=True)

        # Zustand nach Neustart wiederherstellen
        if self._restore_state():
            self.log(
                f"Session wiederhergestellt: gestartet {self._session_start}, "
                f"RFID={self._rfid_at_start}, {len(self._price_samples)} Preissamples"
            )
            self._price_listener = self.listen_state(
                self._on_price_change, self.S_PRICE_KWH)

        self.listen_state(self.on_car_change, self.S_CAR)

        for entity_id in self.PAYMENT_HELPERS.values():
            self.listen_state(self._on_payment_change, entity_id)
        self._init_balances()

        self.log(f"Überwache: {self.S_CAR}, RFID: {self.S_RFID}")

    def on_car_change(self, entity, attribute, old, new, kwargs):
        self.log(f"Car-Status: {old} → {new}")
        if new == "Charging" and not self._session_active:
            self._session_start_handler()
        elif new == "Charging" and self._session_active and self._end_timer:
            # Schnelle Wiederverbindung (<10s) – laufende Session fortsetzen
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

        # Startwerte für Energie- und Kostenberechnung setzen
        eto      = self._float(self.S_ETO)
        integral = self._float(self.S_KOSTEN_INTEGRAL)
        try:
            self.call_service("input_number/set_value",
                              entity_id=self.S_ETO_START, value=eto)
            self.call_service("input_number/set_value",
                              entity_id=self.S_KOSTEN_INTEGRAL_START, value=integral)
        except Exception as e:
            self.log(f"Startwerte setzen fehlgeschlagen: {e}", level="WARNING")

        v = self._float(self.S_PRICE_KWH)
        if v:
            self._price_samples.append({
                "t": self._session_start,
                "v": round(v, 1)
            })

        self._price_listener = self.listen_state(
            self._on_price_change, self.S_PRICE_KWH)

        self._save_state()

        user = self._rfid_to_user(self._rfid_at_start) if self._rfid_at_start else "–"
        self.log(f"Session gestartet: RFID={self._rfid_at_start} ({user}) um {self._session_start}")

    def _on_price_change(self, entity, attribute, old, new, kwargs):
        if self._session_active and new not in (None, "unknown", "unavailable"):
            try:
                self._price_samples.append({
                    "t": datetime.now(timezone.utc).isoformat(),
                    "v": round(float(new), 1)
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

        v = self._float(self.S_PRICE_KWH)
        if v:
            self._price_samples.append({
                "t": datetime.now(timezone.utc).isoformat(),
                "v": round(v, 1)
            })

        rfid = self._rfid_at_start or self._get_rfid()

        # Energie aus ETO-Differenz (Sensor bereits in kWh)
        eto       = self._float(self.S_ETO)
        eto_start = self._float(self.S_ETO_START)
        energy    = round(eto - eto_start, 3) if eto > eto_start else 0.0

        if energy < 0.1:
            self.log(f"Session ignoriert (nur {energy:.3f} kWh)")
            self._reset()
            return

        end_time  = datetime.now(timezone.utc)
        start_dt  = datetime.fromisoformat(self._session_start)
        duration  = int((end_time - start_dt).total_seconds())
        soc       = self._float(self.S_SOC)
        end_time  = end_time.isoformat()

        # Kosten aus Integral-Differenz (Riemann-Summe seit Session-Start)
        integral_now   = self._float(self.S_KOSTEN_INTEGRAL)
        integral_start = self._float(self.S_KOSTEN_INTEGRAL_START)
        kosten_session = round(integral_now - integral_start, 4) if integral_now > integral_start else 0.0
        if kosten_session > 0:
            price_eur = round(kosten_session, 2)
        else:
            # Fallback: Durchschnittspreis × Energie
            avg_price = (sum(s["v"] for s in self._price_samples) / len(self._price_samples)
                         if self._price_samples else self._float(self.S_PRICE_KWH))
            price_eur = round(energy * avg_price / 100, 2) if avg_price else None

        price_kwh = round(price_eur / energy, 4) if (price_eur and energy) else None

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
        if price_eur and user in self.PAYMENT_HELPERS:
            self._add_to_balance(user, price_eur)
        self._reset()

    def _reset(self):
        self._session_start = None
        self._rfid_at_start = None
        self._price_samples = []
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
        return self.RFID_USERS.get(rfid, rfid)

    def _float(self, entity_id):
        try:
            val = self.get_state(entity_id)
            if val in (None, "unknown", "unavailable"):
                return 0.0
            return float(val)
        except Exception:
            return 0.0

    # ── Zustandspersistenz für Neustart-Recovery ──────────────────────────

    def _save_state(self):
        state = {
            "active":        self._session_active,
            "session_start": self._session_start,
            "rfid_at_start": self._rfid_at_start,
            "price_samples": self._price_samples,
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

    # ── Session speichern ─────────────────────────────────────────────────

    def _on_payment_change(self, entity, attribute, old, new, kwargs):
        # Startup-Trigger ignorieren: old ist None (AppDaemon-Start) oder
        # "unavailable"/"unknown" (HA-Neustart, Entity kommt aus unavailable zurück)
        if old in (None, "unavailable", "unknown") or old == new:
            return
        try:
            amount = float(new) if new not in (None, "unknown", "unavailable") else 0.0
        except Exception:
            return
        if amount <= 0:
            return
        user = next((u for u, eid in self.PAYMENT_HELPERS.items() if eid == entity), None)
        if not user:
            return
        balances = self._load_balances()
        balances[user] = round(max(0.0, balances.get(user, 0.0) - amount), 2)
        self._save_balances(balances)
        # Helper zurücksetzen
        try:
            self.call_service("input_number/set_value", entity_id=entity, value=0)
        except Exception as e:
            self.log(f"Helper zurücksetzen fehlgeschlagen: {e}", level="WARNING")
        self.log(f"Zahlung {amount:.2f} € für {user} verbucht, neuer offener Betrag: {balances[user]:.2f} €")

    def _init_balances(self):
        if os.path.exists(self.BALANCES_FILE):
            return
        balances = {user: 0.0 for user in self.PAYMENT_HELPERS}
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
