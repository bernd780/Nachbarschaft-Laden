import appdaemon.plugins.hass.hassapi as hass
from PIL import Image, ImageDraw, ImageOps
from datetime import datetime, timedelta, timezone
import os
import json

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Berlin")
except Exception:
    _TZ = timezone(timedelta(hours=2))

def _local(dt):
    return dt.astimezone(_TZ)

class LadepreisGraph(hass.Hass):

    W       = 460
    H_TOTAL = 136

    SMILEY_MIN = 15
    SMILEY_MID = 32
    SMILEY_MAX = 50

    SMOOTH_MINUTES = 15
    HOURS = 8
    Y_MIN = 10
    Y_MAX = 40

    DISPLAY_W    = 480
    DISPLAY_H    = 800
    HISTORY_HOURS  = 336   # 2 Wochen roh gespeichert
    DISPLAY_HOURS  = 72    # Fenster das ins data.json / Frontend geht

    def initialize(self):
        self.log("LadepreisGraph gestartet (override ok)")

        a = self.args
        # Preisberechnung – Eingangssensoren
        self.S_NETZLEISTUNG      = a.get("sensor_netzleistung",          "sensor.leistung_stromzaehler")
        self.S_WALLBOX_LEISTUNG  = a.get("sensor_wallbox_leistung",      "sensor.go_echarger_XXXXXX_nrg_12")
        self.S_BATTERIE_LEISTUNG = a.get("sensor_batterie_leistung",     "sensor.summe_battery_leistung")
        # Preisberechnung – Konstanten (ct/kWh bzw. kW)
        self.PREIS_EINSPEISUNG   = float(a.get("preis_einspeiseverguetung_ct", 8.0))
        self.PREIS_MARGE         = float(a.get("preis_marge_ct",               6.0))
        self.PREIS_NETZBEZUG     = float(a.get("preis_netzbezug_ct",           30.0))
        self.PREIS_ZIELLEISTUNG  = float(a.get("preis_zielleistung_kw",        11.0))
        self.PREIS_TOTZONE_KW    = 0.5
        self.KERNZEIT_START  = int(a.get("kernzeit_start", 10))
        self.KERNZEIT_ENDE   = int(a.get("kernzeit_ende",  17))
        # PV-Sensoren (optional – leerer String = Feature deaktiviert)
        self.S_PV_MORGEN     = a.get("sensor_pv_morgen",           "sensor.morgenpv")     or None
        self.S_PV_UEBERMORGEN= a.get("sensor_pv_uebermorgen",      "sensor.uebermorgenpv") or None
        self.S_PV_IN3TAGEN   = a.get("sensor_pv_in3tagen",         "sensor.pvin3tagen")   or None
        self.S_PV_HEUTE_KWH  = a.get("sensor_pv_erzeugung_heute",  "sensor.daily_pv_generation")              or None
        self.S_PV_REST_HEUTE = a.get("sensor_pv_rest_heute",       "sensor.pv_rest_heute_noch")               or None
        self.S_PV_PEAK_ZEIT  = a.get("sensor_pv_peak_zeit_heute",  "sensor.power_highest_peak_time_today_3")  or None
        self.S_FAHRZEUG_AKKU = a.get("sensor_fahrzeug_akku",      "sensor.mein_fahrzeug_battery")
        self.S_LADEGERAET    = a.get("sensor_ladegeraet_status",  "sensor.go_echarger_XXXXXX_car")
        self.S_ZAEHLER       = a.get("sensor_zaehlerstand_kwh",   "sensor.go_echarger_XXXXXX_eto")
        self.S_KOSTEN        = a.get("sensor_kosten_integral",    "sensor.go_echarger_kosten_integral_2")
        self.S_SESSION_ENE   = a.get("sensor_session_energie",    "") or None
        self.S_SESSION_DAUER = a.get("sensor_session_dauer",      "") or None
        self.S_SESSION_SOC   = a.get("sensor_session_soc",        "") or None
        self.HAUSVERBRAUCH_DEFAULT = float(a.get("hausverbrauch_kwh", 10.0))
        self.LADEZIEL_DEFAULT      = float(a.get("ladeziel_soc",      80.0))
        self.H_HAUSVERBRAUCH = a.get("helper_hausverbrauch",      "") or None
        self.H_LADEZIEL      = a.get("helper_ladeziel_soc",       "") or None
        self.QR_CODE_URL     = a.get("qr_code_url",               "")
        self.WWW_DIR         = a.get("www_dir",                   "/homeassistant/www/nachbarschaft-laden")
        self.HISTORY_FILE    = os.path.join(self.WWW_DIR, "price_history.json")

        self.render_combined({})
        self.run_every(self.render_combined, "now+300", 5 * 60)
        self.listen_state(self.render_combined, self.S_LADEGERAET)

    def _get_hausverbrauch(self):
        if self.H_HAUSVERBRAUCH:
            v = self._float_safe(self.H_HAUSVERBRAUCH)
            if v > 0:
                return v
        return self.HAUSVERBRAUCH_DEFAULT

    def _get_ladeziel(self):
        if self.H_LADEZIEL:
            v = self._float_safe(self.H_LADEZIEL)
            if v > 0:
                return v
        return self.LADEZIEL_DEFAULT

    def _load_session_state(self):
        path = os.path.join(self.WWW_DIR, "session_active.json")
        try:
            if os.path.exists(path):
                with open(path) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _float_safe(self, entity_id, default=0.0):
        try:
            v = self.get_state(entity_id)
            if v in (None, "unknown", "unavailable"):
                return default
            return float(v)
        except Exception:
            return default

    def calc_surplus(self, pv, soc, haus, ziel):
        auto = max(ziel - soc, 0) * 0.75 / 3
        return pv - haus - auto

    def _load_price_history(self):
        try:
            if os.path.exists(self.HISTORY_FILE):
                with open(self.HISTORY_FILE) as f:
                    return json.load(f)
        except Exception as e:
            self.log(f"History laden fehlgeschlagen: {e}")
        return []

    def _save_price_history(self, history):
        tmp = self.HISTORY_FILE + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(history, f)
            os.replace(tmp, self.HISTORY_FILE)
        except Exception as e:
            self.log(f"History speichern fehlgeschlagen: {e}")

    def smooth_points(self, points, bucket_minutes=None):
        if not points:
            return [], None
        last_raw = points[-1][1]
        bucket_s = (bucket_minutes or self.SMOOTH_MINUTES) * 60
        t0 = points[0][0].timestamp()
        buckets = {}
        for t, v in points:
            idx = int((t.timestamp() - t0) / bucket_s)
            buckets.setdefault(idx, []).append((t, v))
        smoothed = []
        for idx in sorted(buckets):
            grp = buckets[idx]
            avg_v = sum(v for _, v in grp) / len(grp)
            mid_ts = t0 + idx * bucket_s + bucket_s / 2
            mid_t  = datetime.fromtimestamp(mid_ts, tz=timezone.utc)
            smoothed.append((mid_t, avg_v))
        return smoothed, last_raw

    def draw_smiley(self, draw, cx, cy, r, surplus):
        lw = max(r // 10, 4)
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)],
                     fill=(255,255,255), outline=(0,0,0), width=lw)
        ey  = cy - int(r * 0.22)
        exl = cx - int(r * 0.30)
        exr = cx + int(r * 0.30)
        er  = max(int(r * 0.09), 6)
        draw.ellipse([(exl-er, ey-er), (exl+er, ey+er)], fill=(0,0,0))
        draw.ellipse([(exr-er, ey-er), (exr+er, ey+er)], fill=(0,0,0))
        mx = int(r * 0.58)

        if surplus < self.SMILEY_MIN:
            brow_y  = ey - er - int(r * 0.12)
            brow_dx = int(r * 0.22)
            brow_dy = int(r * 0.10)
            draw.line([(exl - brow_dx, brow_y + brow_dy),
                       (exl + brow_dx, brow_y - brow_dy)],
                      fill=(0,0,0), width=lw - 1)
            draw.line([(exr - brow_dx, brow_y - brow_dy),
                       (exr + brow_dx, brow_y + brow_dy)],
                      fill=(0,0,0), width=lw - 1)
            bbox = [cx-mx, cy+int(r*0.28), cx+mx, cy+int(r*0.75)]
            draw.arc(bbox, start=180, end=360, fill=(0,0,0), width=lw)
        elif surplus < self.SMILEY_MID:
            draw.line([(cx-mx, cy+int(r*0.42)), (cx+mx, cy+int(r*0.42))],
                      fill=(0,0,0), width=lw)
        elif surplus < self.SMILEY_MAX:
            bbox = [cx-mx, cy+int(r*0.05), cx+mx, cy+int(r*0.55)]
            draw.arc(bbox, start=0, end=180, fill=(0,0,0), width=lw)
        else:
            bbox = [cx-mx, cy-int(r*0.10), cx+mx, cy+int(r*0.65)]
            draw.arc(bbox, start=0, end=180, fill=(0,0,0), width=lw)

    def _load_font(self, bold, size):
        from PIL import ImageFont
        font_file = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(self.WWW_DIR, "fonts", font_file),
            os.path.join(script_dir, "fonts", font_file),
            f"/usr/share/fonts/truetype/dejavu/{font_file}",
            f"/usr/share/fonts/dejavu/{font_file}",
            f"/usr/share/fonts/TTF/{font_file}",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _render_preview(self, ladepreis, smiley_img, surplus_m, surplus_u, surplus_3):
        W, H = self.DISPLAY_W, self.DISPLAY_H
        FG   = (0, 0, 0)

        img  = Image.new("RGB", (W, H), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        def ct(x, y, text, bold, size):
            draw.text((x, y), text, font=self._load_font(bold, size), fill=FG, anchor="mt")

        # ── Sektion 1: Preis (y=0–267) ──
        ct(240, 4,   "Aktueller Ladepreis",                           True,  28)
        ct(240, 40,  f"{ladepreis:.1f}" if ladepreis is not None else "—",
                                                                       True,  180)
        ct(240, 226, "ct/kWh",                                        False, 40)
        draw.rectangle([(0, 267), (W, 269)], fill=FG)

        # ── Sektion 2: PV-Überschuss (y=267–534) ──
        cx0, cx1, cx2 = 80, 240, 400
        ct(240, 273, "PV-Überschuss Prognose", True, 22)
        ct(cx0, 303, "Morgen",                 True, 22)
        ct(cx1, 303, "Übermorgen",             True, 22)
        ct(cx2, 303, "In 3 Tagen",             True, 22)

        img.paste(smiley_img, (10, 330))

        for cx, surplus in [(cx0, surplus_m), (cx1, surplus_u), (cx2, surplus_3)]:
            ct(cx, 470, f"+{max(0.0, surplus):.0f} kWh", True, 28)
        draw.rectangle([(0, 534), (W, 536)], fill=FG)

        # ── Sektion 3: Footer (y=534–800) ──
        now = datetime.now()
        ct(240, 540, now.strftime("%H:%M"),    True,  28)
        ct(240, 578, now.strftime("%d.%m.%Y"), False, 20)

        # Logo links: x=0, y=644, 336×118px
        LOGO_W, LOGO_H = 336, 118
        logo_drawn = False
        try:
            logo_img = Image.open(os.path.join(self.WWW_DIR, "logo_display.png")).convert("RGB")
            logo_w, logo_h = logo_img.size
            scale = min(LOGO_W / logo_w, LOGO_H / logo_h)
            new_w = int(logo_w * scale)
            new_h = int(logo_h * scale)
            logo_img = logo_img.resize((new_w, new_h), Image.LANCZOS)
            lx = (LOGO_W - new_w) // 2
            ly = 644 + (LOGO_H - new_h) // 2
            img.paste(logo_img, (lx, ly))
            logo_drawn = True
            self.log(f"Logo geladen ({new_w}x{new_h})")
        except Exception as e:
            self.log(f"Logo nicht ladbar: {e}")

        if not logo_drawn:
            lx, ly = 20, 644
            draw.rectangle([(lx+10, ly+38), (lx+90, ly+88)], fill=FG)
            draw.polygon([(lx, ly+40), (lx+50, ly), (lx+100, ly+40)], fill=FG)
            draw.polygon([(lx+7, ly+40), (lx+50, ly+8), (lx+93, ly+40)], fill=(255,255,255))
            draw.rectangle([(lx+10, ly+38), (lx+90, ly+88)], outline=FG, width=3)
            draw.rectangle([(lx+15, ly+48), (lx+40, ly+70)], outline=FG, width=2)
            draw.line([(lx+27, ly+48), (lx+27, ly+70)], fill=FG, width=2)
            draw.line([(lx+15, ly+59), (lx+40, ly+59)], fill=FG, width=2)
            draw.rectangle([(lx+55, ly+60), (lx+78, ly+88)], outline=FG, width=2)
            draw.rectangle([(lx+92, ly+28), (lx+115, ly+88)], outline=FG, width=2)
            draw.rectangle([(lx+97, ly+34), (lx+110, ly+50)], fill=FG)
            draw.polygon([(lx+104,ly+54),(lx+98,ly+66),(lx+103,ly+66),
                          (lx+100,ly+76),(lx+111,ly+62),(lx+106,ly+62)], fill=FG)
            ct(230, 649, "Nachbarschaft-", True, 26)
            ct(230, 687, "Laden",          True, 34)

        # QR rechts neben Logo: x=342, y=637, ~132×132px (scale 4)
        try:
            import qrcode as _qr
            qr = _qr.QRCode(error_correction=_qr.constants.ERROR_CORRECT_M,
                             box_size=4, border=0)
            qr.add_data(self.QR_CODE_URL)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            qr_img = qr_img.resize((132, 132), Image.LANCZOS)
            img.paste(qr_img, (342, 637))
        except Exception as e:
            self.log(f"QR-Code nicht verfügbar: {e}")

        out = os.path.join(self.WWW_DIR, "display_preview.png")
        tmp = out + ".tmp"
        img.save(tmp, "PNG")
        os.replace(tmp, out)
        self.log(f"Display-Preview gespeichert: {out}")

        # HA-Kamera-Entity liest noch aus dem alten Pfad – dort ebenfalls schreiben
        legacy_dir = "/homeassistant/www/nachbarschaftsladen"
        if os.path.isdir(legacy_dir):
            import shutil
            shutil.copy2(out, os.path.join(legacy_dir, "display_preview.png"))

    def _berechne_ladepreis(self):
        """Dynamischer Ladepreis basierend auf PV-Überschuss (ct/kWh)."""
        zaehler_w = self._float_safe(self.S_NETZLEISTUNG)
        wallbox_w = self._float_safe(self.S_WALLBOX_LEISTUNG)
        akku_w    = self._float_safe(self.S_BATTERIE_LEISTUNG)

        akku_entladung_w = max(akku_w, 0.0)
        ueberschuss_w    = wallbox_w - zaehler_w - akku_entladung_w
        ueberschuss_kw   = max(ueberschuss_w, 0.0) / 1000.0
        preis_max = self.PREIS_NETZBEZUG + self.PREIS_MARGE
        if ueberschuss_kw < self.PREIS_TOTZONE_KW:
            return round(preis_max, 2)
        ueberschuss      = min(ueberschuss_kw / self.PREIS_ZIELLEISTUNG, 1.0)

        preis_min = self.PREIS_EINSPEISUNG + self.PREIS_MARGE
        preis     = preis_max - ueberschuss * (preis_max - preis_min)
        return round(max(preis_min, min(preis_max, preis)), 2)

    def render_combined(self, kwargs):
        self.log("Rendere Smiley-Bild...")

        ladepreis = None
        try:
            ladepreis = self._berechne_ladepreis()
        except Exception:
            pass

        pv_m = self._float_safe(self.S_PV_MORGEN)     if self.S_PV_MORGEN     else 0.0
        pv_u = self._float_safe(self.S_PV_UEBERMORGEN) if self.S_PV_UEBERMORGEN else 0.0
        pv_3 = self._float_safe(self.S_PV_IN3TAGEN)   if self.S_PV_IN3TAGEN   else 0.0
        soc  = self._float_safe(self.S_FAHRZEUG_AKKU)
        haus = self._get_hausverbrauch()
        ziel = self._get_ladeziel()

        surplus_m = self.calc_surplus(pv_m, soc, haus, ziel)
        surplus_u = self.calc_surplus(pv_u, soc, haus, ziel)
        surplus_3 = self.calc_surplus(pv_3, soc, haus, ziel)

        img  = Image.new("RGB", (self.W, self.H_TOTAL), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        col_w  = self.W // 3
        radius = 62
        cy_sm  = 68

        for i, surplus in enumerate([surplus_m, surplus_u, surplus_3]):
            cx = col_w * i + col_w // 2
            self.draw_smiley(draw, cx, cy_sm, radius, surplus)

        output_path = os.path.join(self.WWW_DIR, "display_combined.png")
        tmp_path    = output_path + ".tmp"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img_gray = img.convert("L")
        img_inv  = ImageOps.invert(img_gray)
        img_inv.convert("1").save(tmp_path, "PNG")
        os.replace(tmp_path, output_path)
        self.log(f"Smiley-Bild gespeichert: {output_path} | m={surplus_m:.0f} u={surplus_u:.0f} 3={surplus_3:.0f}")

        try:
            if ladepreis is not None:
                self.set_state("sensor.nl_ladepreis_aktuell", state=round(ladepreis, 1),
                               attributes={"unit_of_measurement": "ct/kWh",
                                           "state_class": "measurement",
                                           "friendly_name": "NL Ladepreis aktuell"})
            self.set_state("sensor.nl_hausverbrauch_kwh", state=round(haus, 1),
                           attributes={"unit_of_measurement": "kWh",
                                       "friendly_name": "NL Hausverbrauch tägl."})
            self.set_state("sensor.nl_ladeziel_soc", state=round(ziel, 0),
                           attributes={"unit_of_measurement": "%",
                                       "friendly_name": "NL Ladeziel SOC"})
            self.set_state("sensor.nl_fahrzeug_soc", state=round(soc, 0),
                           attributes={"unit_of_measurement": "%",
                                       "state_class": "measurement",
                                       "friendly_name": "NL Fahrzeug SOC"})
            self.set_state("sensor.nl_surplus_morgen", state=round(max(0.0, surplus_m), 1),
                           attributes={"unit_of_measurement": "kWh",
                                       "friendly_name": "NL PV-Überschuss Morgen"})
            self.set_state("sensor.nl_surplus_uebermorgen", state=round(max(0.0, surplus_u), 1),
                           attributes={"unit_of_measurement": "kWh",
                                       "friendly_name": "NL PV-Überschuss Übermorgen"})
            self.set_state("sensor.nl_surplus_in3tagen", state=round(max(0.0, surplus_3), 1),
                           attributes={"unit_of_measurement": "kWh",
                                       "friendly_name": "NL PV-Überschuss In 3 Tagen"})
        except Exception as e:
            self.log(f"HA-State-Publish fehlgeschlagen: {e}", level="WARNING")

        try:
            self._render_preview(ladepreis, img, surplus_m, surplus_u, surplus_3)
        except Exception as e:
            self.log(f"Preview-Fehler: {e}", level="ERROR")

        try:
            end_dt = datetime.now(timezone.utc)
            cutoff = end_dt - timedelta(hours=self.HISTORY_HOURS)

            history_raw = self._load_price_history()
            if ladepreis is not None and self.Y_MIN <= ladepreis <= self.Y_MAX:
                history_raw.append({"t": end_dt.isoformat(), "v": ladepreis})
            history_raw = [p for p in history_raw
                           if datetime.fromisoformat(p["t"]) >= cutoff]
            self._save_price_history(history_raw)

            raw_points = [(datetime.fromisoformat(p["t"]), p["v"]) for p in history_raw]

            cutoff_kurz = end_dt - timedelta(hours=6)
            raw_kurz    = [(t, v) for t, v in raw_points if t >= cutoff_kurz]
            pts_kurz, last_raw_val = self.smooth_points(raw_kurz)
            verlauf = [{"t": t.isoformat(), "v": round(v, 2)} for t, v in pts_kurz]
            aktuell = round(float(last_raw_val), 1) if last_raw_val is not None else None

            cutoff_display = end_dt - timedelta(hours=self.DISPLAY_HOURS)
            raw_display  = [(t, v) for t, v in raw_points if t >= cutoff_display]
            pts_lang, _ = self.smooth_points(raw_display, bucket_minutes=60)
            verlauf_lang = [{"t": t.isoformat(), "v": round(v, 2)} for t, v in pts_lang]

            cutoff_8h = end_dt - timedelta(hours=self.HOURS)
            raw_8h    = [(t, v) for t, v in raw_points if t >= cutoff_8h]
            peak_pts  = [(t, v) for t, v in raw_8h if self.KERNZEIT_START <= _local(t).hour < self.KERNZEIT_ENDE]
            peak_avg  = round(sum(v for _, v in peak_pts) / len(peak_pts), 1) if peak_pts else None

            gestern    = (_local(end_dt) - timedelta(days=1)).date()
            vortag_pts = [(t, v) for t, v in raw_points
                          if _local(t).date() == gestern
                          and self.KERNZEIT_START <= _local(t).hour < self.KERNZEIT_ENDE]
            vortag_avg = round(sum(v for _, v in vortag_pts) / len(vortag_pts), 1) if vortag_pts else None
            self.log(f"Vortag ({gestern}) {self.KERNZEIT_START}–{self.KERNZEIT_ENDE}h: {len(vortag_pts)} Punkte, avg={vortag_avg}")

            guenstigste_stunde_gestern = None
            if vortag_pts:
                best_avg_g, best_start_g = None, None
                for t_start, _ in vortag_pts:
                    t_end = t_start + timedelta(hours=1)
                    fenster_pts = [(t, v) for t, v in vortag_pts if t_start <= t < t_end]
                    if len(fenster_pts) >= 4:
                        avg = sum(v for _, v in fenster_pts) / len(fenster_pts)
                        if best_avg_g is None or avg < best_avg_g:
                            best_avg_g   = avg
                            best_start_g = t_start
                if best_start_g:
                    guenstigste_stunde_gestern = {
                        "start":  _local(best_start_g).isoformat(),
                        "avg_ct": round(best_avg_g, 1),
                    }

            heute_lokal  = _local(end_dt).date()
            haupt_pts    = [(t, v) for t, v in raw_points
                            if _local(t).date() == heute_lokal
                            and self.KERNZEIT_START <= _local(t).hour < self.KERNZEIT_ENDE]
            guenstigste_stunde = None
            if haupt_pts:
                best_avg, best_start = None, None
                fenster = timedelta(hours=1)
                for i, (t_start, _) in enumerate(haupt_pts):
                    t_end   = t_start + fenster
                    fenster_pts = [(t, v) for t, v in haupt_pts if t_start <= t < t_end]
                    if len(fenster_pts) >= 4:
                        avg = sum(v for _, v in fenster_pts) / len(fenster_pts)
                        if best_avg is None or avg < best_avg:
                            best_avg   = avg
                            best_start = t_start
                if best_start:
                    guenstigste_stunde = {
                        "start":  _local(best_start).isoformat(),
                        "avg_ct": round(best_avg, 1),
                    }

            vor_hauptzeit = _local(end_dt).hour < (self.KERNZEIT_ENDE - 1)

            guenstigste_stunde_voraussichtlich = None
            if self.S_PV_PEAK_ZEIT:
                try:
                    peak_raw = self.get_state(self.S_PV_PEAK_ZEIT)
                    if peak_raw not in (None, "unknown", "unavailable"):
                        peak_utc   = datetime.fromisoformat(peak_raw.replace("Z", "+00:00"))
                        peak_local = _local(peak_utc)
                        peak_h     = max(self.KERNZEIT_START, min(self.KERNZEIT_ENDE - 1, peak_local.hour))
                        ld = _local(end_dt)
                        peak_start = datetime(ld.year, ld.month, ld.day, peak_h, 0, 0, tzinfo=_TZ)
                        guenstigste_stunde_voraussichtlich = {"start": peak_start.isoformat()}
                except Exception as e:
                    self.log(f"Peak-Zeit Fehler: {e}")

            pv_erzeugung_prozent = None
            if self.S_PV_HEUTE_KWH and self.S_PV_REST_HEUTE:
                try:
                    h = datetime.now(_TZ).hour
                    if 4 <= h < 23:
                        erzeugt = self._float_safe(self.S_PV_HEUTE_KWH)
                        rest    = self._float_safe(self.S_PV_REST_HEUTE)
                        gesamt  = erzeugt + rest
                        if gesamt > 0.5:
                            pv_erzeugung_prozent = round(min(erzeugt / gesamt * 100.0, 100.0), 1)
                except Exception:
                    pass

            ladevorgang = {"aktiv": False, "verbunden": False,
                           "energie_kwh": None, "dauer_s": None, "soc": None,
                           "kosten_session": None}
            try:
                car = self.get_state(self.S_LADEGERAET)
                ladevorgang["aktiv"]     = (car == "Charging")
                ladevorgang["verbunden"] = car in ("Charging", "Complete", "Wait for car")

                session_state = self._load_session_state()
                try:
                    eto         = float(self.get_state(self.S_ZAEHLER) or 0)
                    eto_start   = float(session_state.get("eto_start", 0))
                    energie_kwh = eto - eto_start
                    if eto_start > 0 and energie_kwh > 0:
                        ladevorgang["energie_kwh"] = round(energie_kwh, 2)
                except Exception:
                    if self.S_SESSION_ENE:
                        v = self.get_state(self.S_SESSION_ENE)
                        if v not in (None, "unavailable", "unknown"):
                            ladevorgang["energie_kwh"] = round(float(v), 2)

                try:
                    integral_now   = float(self.get_state(self.S_KOSTEN) or 0)
                    integral_start = float(session_state.get("integral_start", 0))
                    if integral_start > 0 and integral_now > integral_start:
                        ladevorgang["kosten_session"] = round(integral_now - integral_start, 4)
                except Exception:
                    pass

                for key, sensor, digits in [
                    ("dauer_s", self.S_SESSION_DAUER, 0),
                    ("soc",     self.S_SESSION_SOC,   0),
                ]:
                    if sensor:
                        v = self.get_state(sensor)
                        if v not in (None, "unavailable", "unknown"):
                            ladevorgang[key] = round(float(v), digits)
            except Exception as e:
                self.log(f"Ladevorgang-Fehler: {e}")

            preis_max = round(self.PREIS_NETZBEZUG + self.PREIS_MARGE, 2)
            preis_min = round(self.PREIS_EINSPEISUNG + self.PREIS_MARGE, 2)
            data = {
                "generated": end_dt.isoformat(),
                "ladepreis_aktuell":    aktuell,
                "ladepreis_max":        preis_max,
                "ladepreis_min":        preis_min,
                "ladepreis_peak_avg":   peak_avg,
                "ladepreis_vortag_avg": vortag_avg,
                "guenstigste_stunde":              guenstigste_stunde,
                "guenstigste_stunde_gestern":      guenstigste_stunde_gestern,
                "guenstigste_stunde_voraussichtlich": guenstigste_stunde_voraussichtlich,
                "vor_hauptzeit":                   vor_hauptzeit,
                "kernzeit": {"start": self.KERNZEIT_START, "ende": self.KERNZEIT_ENDE},
                "features": {
                    "pv_forecast": bool(self.S_PV_MORGEN and self.S_PV_UEBERMORGEN and self.S_PV_IN3TAGEN),
                    "pv_arc":      bool(self.S_PV_HEUTE_KWH and self.S_PV_REST_HEUTE),
                    "pv_peak":     bool(self.S_PV_PEAK_ZEIT),
                },
                "verlauf":              verlauf,
                "verlauf_lang":         verlauf_lang,
                "pv": {
                    "morgen":      round(max(0.0, surplus_m), 1),
                    "uebermorgen": round(max(0.0, surplus_u), 1),
                    "in3tagen":    round(max(0.0, surplus_3), 1),
                    "erzeugung_prozent": pv_erzeugung_prozent,
                },
                "ladevorgang": ladevorgang,
            }
            json_path = os.path.join(self.WWW_DIR, "data.json")
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, "w") as f:
                json.dump(data, f)
            self.log(f"JSON ok: aktuell={aktuell}, peak_avg={peak_avg}, vortag_avg={vortag_avg}")
        except Exception as e:
            self.log(f"JSON-Fehler: {e}", level="ERROR")
