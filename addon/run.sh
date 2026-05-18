#!/usr/bin/with-contenv bashio
set -e

OPTIONS="/data/options.json"
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

# ── Optionen auslesen ─────────────────────────────────────────────────────────
OPTS="$OPTIONS"

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
if ls /www/*.html 1>/dev/null 2>&1; then
  for _f in /www/*.html; do
    sed "s|https://nachbarschaft-laden.de|${BASIS_URL}|g" "$_f" > "$WWW/$(basename "$_f")"
  done
fi

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
    bashio::log.info "Zahlungs-Helper input_number.${object_id} bereits vorhanden"
    return
  fi

  local body
  body=$(printf '{"id":"%s","name":"%s","min":%s,"max":%s,"step":%s,"mode":"box"}' \
    "$object_id" "$name" "$min" "$max" "$step")

  if curl -sf -X POST \
       -H "$auth" -H "Content-Type: application/json" \
       -d "$body" \
       "${url}/config/input_number/config" > /dev/null 2>&1; then
    bashio::log.info "Zahlungs-Helper input_number.${object_id} angelegt"
  else
    bashio::log.warning "Zahlungs-Helper input_number.${object_id} konnte nicht angelegt werden"
  fi
}

# Nur warten und Helper anlegen, wenn RFID-Nutzer mit payment_helper konfiguriert sind
RFID_MIT_HELPER=$(jq '[.rfid_benutzer // [] | .[] | select((.payment_helper // "") != "")] | length' "$OPTS")

if [ "$RFID_MIT_HELPER" -gt 0 ]; then
  bashio::log.info "Warte auf Home Assistant API ..."
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
fi

bashio::log.info "Starte AppDaemon ..."
exec appdaemon -c "$AD_CONF"
