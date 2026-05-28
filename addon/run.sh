#!/usr/bin/with-contenv /bin/sh
set -e

log() { echo "[$(date '+%H:%M:%S')] $*"; }

OPTIONS="/data/options.json"
BACKUP_FILE="/homeassistant/nachbarschaft_laden_konfiguration.json"
AD_CONF="/config_ad"
APPS_DIR="/homeassistant/.addon_nachbarschaft_laden/apps"

mkdir -p "$AD_CONF"
mkdir -p "$APPS_DIR"

# ── AppDaemon-Hauptkonfiguration ──────────────────────────────────────────────
cat > "$AD_CONF/appdaemon.yaml" <<EOF
appdaemon:
  latitude: 48.0
  longitude: 11.0
  elevation: 500
  time_zone: Europe/Berlin
  plugins:
    HASS:
      type: hass
      ha_url: http://supervisor/core
      token: ${SUPERVISOR_TOKEN}
  app_dir: $APPS_DIR

http:
  url: http://127.0.0.1:5050

logs:
  main_log:
    filename: /proc/1/fd/1
    log_level: INFO
EOF

# ── Konfiguration sichern / wiederherstellen ──────────────────────────────────
OPTS="$OPTIONS"

# Frische Installation erkennen: Platzhalter-Sensor-ID im Feld sensor_ladegeraet_status
_SENSOR=$(jq -r '.sensor_ladegeraet_status // ""' "$OPTIONS")
if echo "$_SENSOR" | grep -q "XXXXXX" && [ -f "$BACKUP_FILE" ]; then
  log "Neue Installation erkannt – stelle Konfiguration aus Backup wieder her ..."
  cp "$BACKUP_FILE" "$OPTIONS"
  # Supervisor-Store aktualisieren, damit HA-UI korrekte Werte zeigt
  _api_body=$(jq -c '{options: .}' "$BACKUP_FILE")
  if curl -sf -X POST \
       -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
       -H "Content-Type: application/json" \
       -d "$_api_body" \
       "http://supervisor/addons/self/options" > /dev/null 2>&1; then
    log "Supervisor-Store aktualisiert – HA-UI nach Seitenneuladen korrekt"
  else
    log "Warnung: Supervisor-API nicht erreichbar – HA-UI zeigt ggf. noch Platzhalter"
  fi
fi

# Aktuelle (oder wiederhergestellte) Konfiguration sichern
if [ "$OPTS" != "$BACKUP_FILE" ]; then
  cp "$OPTS" "$BACKUP_FILE"
  log "Konfiguration gesichert: $BACKUP_FILE"
fi

# ── Optionen auslesen ─────────────────────────────────────────────────────────

# Preisberechnung
SENSOR_NETZLEISTUNG=$(jq -r '.sensor_netzleistung'          "$OPTS")
SENSOR_WALLBOX_LEISTUNG=$(jq -r '.sensor_wallbox_leistung'  "$OPTS")
SENSOR_BATTERIE_LEISTUNG=$(jq -r '.sensor_batterie_leistung' "$OPTS")
PREIS_EINSPEISUNG=$(jq -r '.preis_einspeiseverguetung_ct'   "$OPTS")
PREIS_MARGE=$(jq -r '.preis_marge_ct'                       "$OPTS")
PREIS_NETZBEZUG=$(jq -r '.preis_netzbezug_ct'               "$OPTS")
PREIS_ZIELLEISTUNG=$(jq -r '.preis_zielleistung_kw'         "$OPTS")

# PV-Prognose
SENSOR_PV_MORGEN=$(jq -r '.sensor_pv_morgen'                "$OPTS")
SENSOR_PV_UEBERMORGEN=$(jq -r '.sensor_pv_uebermorgen'      "$OPTS")
SENSOR_PV_IN3TAGEN=$(jq -r '.sensor_pv_in3tagen'            "$OPTS")
SENSOR_PV_HEUTE=$(jq -r '.sensor_pv_erzeugung_heute'        "$OPTS")
SENSOR_PV_REST_HEUTE=$(jq -r '.sensor_pv_rest_heute'        "$OPTS")
SENSOR_PV_PEAK_ZEIT=$(jq -r '.sensor_pv_peak_zeit_heute'    "$OPTS")

# Kernzeit
KERNZEIT_START=$(jq -r '.kernzeit_start // 10'              "$OPTS")
KERNZEIT_ENDE=$(jq -r '.kernzeit_ende  // 17'               "$OPTS")

# Fahrzeug & Ladestation
SENSOR_FAHRZEUG_AKKU=$(jq -r '.sensor_fahrzeug_akku'        "$OPTS")
SENSOR_LADEGERAET=$(jq -r '.sensor_ladegeraet_status'       "$OPTS")
SENSOR_ZAEHLER=$(jq -r '.sensor_zaehlerstand_kwh'           "$OPTS")
SENSOR_KOSTEN=$(jq -r '.sensor_kosten_integral'             "$OPTS")
SENSOR_RFID=$(jq -r '.sensor_rfid_karte'                    "$OPTS")

# evcc (optional)
SENSOR_SESSION_ENERGIE=$(jq -r '.sensor_session_energie'    "$OPTS")
SENSOR_SESSION_DAUER=$(jq -r '.sensor_session_dauer'        "$OPTS")
SENSOR_SESSION_SOC=$(jq -r '.sensor_session_soc'            "$OPTS")

# Standardwerte & optionale HA-Entities
HAUSVERBRAUCH_KWH=$(jq -r '.hausverbrauch_kwh'              "$OPTS")
LADEZIEL_SOC=$(jq -r '.ladeziel_soc'                        "$OPTS")
HELPER_HAUS=$(jq -r '.helper_hausverbrauch'                 "$OPTS")
HELPER_LADEZIEL=$(jq -r '.helper_ladeziel_soc'              "$OPTS")

# Ausgabe
BASIS_URL=$(jq -r '.basis_url'                               "$OPTS")
QR_CODE_URL=$(jq -r '.qr_code_url'                          "$OPTS")
WEB_UNTERVERZEICHNIS=$(jq -r '.web_unterverzeichnis'        "$OPTS")
WWW="/homeassistant/www/$WEB_UNTERVERZEICHNIS"

# Sessions-Passwort → SHA-256-Hash (leer = kein Schutz → "disabled")
_PW=$(jq -r '.sessions_passwort // ""' "$OPTS")
if [ -n "$_PW" ]; then
  SESSIONS_HASH=$(printf '%s' "$_PW" | sha256sum | cut -d' ' -f1)
else
  SESSIONS_HASH="disabled"
fi

# ── Apps-Konfiguration generieren ─────────────────────────────────────────────
cat > "$APPS_DIR/apps.yaml" <<EOF
ladepreis_graph:
  module: ladepreis_graph
  class: LadepreisGraph
  sensor_netzleistung: "$SENSOR_NETZLEISTUNG"
  sensor_wallbox_leistung: "$SENSOR_WALLBOX_LEISTUNG"
  sensor_batterie_leistung: "$SENSOR_BATTERIE_LEISTUNG"
  preis_einspeiseverguetung_ct: $PREIS_EINSPEISUNG
  preis_marge_ct: $PREIS_MARGE
  preis_netzbezug_ct: $PREIS_NETZBEZUG
  preis_zielleistung_kw: $PREIS_ZIELLEISTUNG
  sensor_pv_morgen: "$SENSOR_PV_MORGEN"
  sensor_pv_uebermorgen: "$SENSOR_PV_UEBERMORGEN"
  sensor_pv_in3tagen: "$SENSOR_PV_IN3TAGEN"
  sensor_pv_erzeugung_heute: "$SENSOR_PV_HEUTE"
  sensor_pv_rest_heute: "$SENSOR_PV_REST_HEUTE"
  sensor_pv_peak_zeit_heute: "$SENSOR_PV_PEAK_ZEIT"
  kernzeit_start: $KERNZEIT_START
  kernzeit_ende: $KERNZEIT_ENDE
  sensor_fahrzeug_akku: "$SENSOR_FAHRZEUG_AKKU"
  sensor_ladegeraet_status: "$SENSOR_LADEGERAET"
  sensor_zaehlerstand_kwh: "$SENSOR_ZAEHLER"
  sensor_kosten_integral: "$SENSOR_KOSTEN"
  sensor_session_energie: "$SENSOR_SESSION_ENERGIE"
  sensor_session_dauer: "$SENSOR_SESSION_DAUER"
  sensor_session_soc: "$SENSOR_SESSION_SOC"
  hausverbrauch_kwh: $HAUSVERBRAUCH_KWH
  ladeziel_soc: $LADEZIEL_SOC
  helper_hausverbrauch: "$HELPER_HAUS"
  helper_ladeziel_soc: "$HELPER_LADEZIEL"
  qr_code_url: "$QR_CODE_URL"
  www_dir: "$WWW"

ladeSession:
  module: ladeSession
  class: LadeSession
  sensor_netzleistung: "$SENSOR_NETZLEISTUNG"
  sensor_wallbox_leistung: "$SENSOR_WALLBOX_LEISTUNG"
  sensor_batterie_leistung: "$SENSOR_BATTERIE_LEISTUNG"
  preis_einspeiseverguetung_ct: $PREIS_EINSPEISUNG
  preis_marge_ct: $PREIS_MARGE
  preis_netzbezug_ct: $PREIS_NETZBEZUG
  preis_zielleistung_kw: $PREIS_ZIELLEISTUNG
  sensor_ladegeraet_status: "$SENSOR_LADEGERAET"
  sensor_zaehlerstand_kwh: "$SENSOR_ZAEHLER"
  sensor_kosten_integral: "$SENSOR_KOSTEN"
  sensor_rfid_karte: "$SENSOR_RFID"
  sensor_session_soc: "$SENSOR_SESSION_SOC"
  www_dir: "$WWW"
  rfid_benutzer:
$(jq -r '
  .rfid_benutzer // [] |
  .[] |
  "    \"" + .rfid + "\": \"" + .name + "\""
' "$OPTS")
  zahlungs_helpers:
$(jq -r '
  .rfid_benutzer // [] |
  .[] |
  "    \"" + .name + "\": \"" + .payment_helper + "\""
' "$OPTS")
EOF

cp /apps/*.py "$APPS_DIR/"

mkdir -p "$WWW"
for _f in /www/*; do
  [ -f "$_f" ] || continue
  case "$_f" in
    *.html)
      sed \
        "s|https://nachbarschaft-laden.de|${BASIS_URL}|g; \
         s|__SESSIONS_PASSWORT_HASH__|${SESSIONS_HASH}|g" \
        "$_f" > "$WWW/$(basename "$_f")"
      ;;
    *)
      cp "$_f" "$WWW/$(basename "$_f")"
      ;;
  esac
done

# ── Zahlungs-Helper in Home Assistant anlegen ─────────────────────────────────
# Legt für jeden konfigurierten RFID-Nutzer automatisch einen input_number-Helper
# an, falls er noch nicht existiert. Der Nutzer trägt dort Zahlungseingänge ein.

ha_create_helper() {
  local object_id="$1" name="$2" min="$3" max="$4" step="$5"
  local url="http://supervisor/core/api"
  local auth="Authorization: Bearer ${SUPERVISOR_TOKEN}"

  local status
  status=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "$auth" "${url}/states/input_number.${object_id}" 2>/dev/null)

  if [ "$status" = "200" ]; then
    log "Zahlungs-Helper input_number.${object_id} bereits vorhanden"
    return
  fi

  local body
  body=$(printf '{"id":"%s","name":"%s","min":%s,"max":%s,"step":%s,"mode":"box"}' \
    "$object_id" "$name" "$min" "$max" "$step")

  if curl -sf -X POST \
       -H "$auth" -H "Content-Type: application/json" \
       -d "$body" \
       "${url}/config/input_number/config" > /dev/null 2>&1; then
    log "Zahlungs-Helper input_number.${object_id} angelegt"
  else
    log "Zahlungs-Helper input_number.${object_id} konnte nicht angelegt werden"
  fi
}

# Zahlungs-Helper im Hintergrund anlegen (blockiert den Start nicht)
RFID_MIT_HELPER=$(jq '[.rfid_benutzer // [] | .[] | select((.payment_helper // "") != "")] | length' "$OPTS")

if [ "$RFID_MIT_HELPER" -gt 0 ]; then
  (
    log "Warte auf Home Assistant API (Hintergrund) ..."
    until curl -sf -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
         "http://supervisor/core/api/" > /dev/null 2>&1; do
      sleep 5
    done

    jq -c '.rfid_benutzer // [] | .[] | select((.payment_helper // "") != "")' "$OPTS" \
    | while IFS= read -r entry; do
        name=$(printf '%s' "$entry" | jq -r '.name')
        helper=$(printf '%s' "$entry" | jq -r '.payment_helper')
        object_id="${helper#input_number.}"
        ha_create_helper "$object_id" "NL Bezahlt $name" 0 9999 0.01
      done
  ) &
fi

# ── Passwort-Watcher: HTML neu schreiben wenn sessions_passwort geändert wird ──
(
  _known_hash="${SESSIONS_HASH}"
  while true; do
    sleep 30
    _pw=$(jq -r '.sessions_passwort // ""' "$OPTIONS" 2>/dev/null)
    if [ -n "$_pw" ]; then
      _cur_hash=$(printf '%s' "$_pw" | sha256sum | cut -d' ' -f1)
    else
      _cur_hash="disabled"
    fi
    if [ "$_cur_hash" != "$_known_hash" ]; then
      _known_hash="$_cur_hash"
      log "Sessions-Passwort geändert – HTML wird aktualisiert ..."
      for _f in /www/*.html; do
        [ -f "$_f" ] || continue
        sed \
          "s|https://nachbarschaft-laden.de|${BASIS_URL}|g; \
           s|__SESSIONS_PASSWORT_HASH__|${_cur_hash}|g" \
          "$_f" > "$WWW/$(basename "$_f")"
      done
      log "HTML aktualisiert (neue Hash-Prefix: ${_cur_hash:0:8}...)"
    fi
  done
) &

log "Starte AppDaemon ..."
exec appdaemon -c "$AD_CONF"
