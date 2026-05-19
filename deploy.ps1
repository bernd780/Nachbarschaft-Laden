$HA_HOST   = "<HA-IP-ADRESSE>"
$HA_USER   = "root"
$ADDON_DIR = "/addons/nachbarschaft-laden"
# Nach Code-Änderungen: git push, dann .\deploy.ps1 [addon|hotdeploy]
# Das Skript löst store-reload + rebuild via HA-API aus.

function Deploy($local, $remote) {
    Write-Host "  $local" -ForegroundColor Cyan
    scp $local "${HA_USER}@${HA_HOST}:${remote}"
    if ($LASTEXITCODE -ne 0) { Write-Error "Fehler bei: $local"; exit 1 }
}

function RunSsh($cmd) {
    & ssh "${HA_USER}@${HA_HOST}" $cmd
    if ($LASTEXITCODE -ne 0) { Write-Error "SSH-Fehler: $cmd"; exit 1 }
}

# ── Auswahl ───────────────────────────────────────────────────────────────────
$target = $args[0]
if (-not $target) { $target = "addon" }

# ── Add-on deployen (lokale Dateien → HA Supervisor) ─────────────────────────
# Setzt voraus: git push wurde vorher ausgeführt.
# Kopiert config.yaml, CHANGELOG.md, run.sh ins lokale Add-on-Verzeichnis,
# dann store-reload + update/rebuild.
if ($target -eq "addon") {
    Write-Host "`nDeploy Add-on (lokale Dateien → HA)" -ForegroundColor Green

    Deploy "addon\config.yaml"    "$ADDON_DIR/config.yaml"
    Deploy "addon\CHANGELOG.md"   "$ADDON_DIR/CHANGELOG.md"
    Deploy "addon\run.sh"         "$ADDON_DIR/run.sh"

    Write-Host "  Supervisor Store reload..." -ForegroundColor Cyan
    $storeResult = & ssh "${HA_USER}@${HA_HOST}" "curl -sf -X POST -H 'Authorization: Bearer \$SUPERVISOR_TOKEN' http://supervisor/store/reload"
    if ($LASTEXITCODE -ne 0) { Write-Warning "store/reload fehlgeschlagen: $storeResult" }

    $info    = & ssh "${HA_USER}@${HA_HOST}" "ha apps info local_nachbarschaft_laden 2>/dev/null"
    $version = ($info | Select-String 'version:'        | Select-Object -First 1).Line.Split(':')[1].Trim()
    $latest  = ($info | Select-String 'version_latest:' | Select-Object -First 1).Line.Split(':')[1].Trim()
    Write-Host "  Installiert: $version  |  Verfügbar: $latest" -ForegroundColor Cyan

    if ($version -ne $latest) {
        Write-Host "  Starte Update auf $latest ..." -ForegroundColor Cyan
        RunSsh "ha apps update local_nachbarschaft_laden 2>&1"
    } else {
        Write-Host "  Gleiche Version – führe Rebuild durch ..." -ForegroundColor Cyan
        RunSsh "ha apps rebuild local_nachbarschaft_laden 2>&1"
    }
    Write-Host "  Add-on aktualisiert. Logs: ha apps logs local_nachbarschaft_laden" -ForegroundColor Cyan
}

# ── Hot-Deploy Python Apps (kein Docker-Rebuild nötig) ───────────────────────
# /homeassistant/.addon_nachbarschaft_laden/apps ist bind-gemountet.
# AppDaemon lädt geänderte .py Dateien automatisch neu.
$HA_ADDON_APPS = "/homeassistant/.addon_nachbarschaft_laden/apps"
if ($target -eq "hotdeploy") {
    Write-Host "`nHot-Deploy Python Apps" -ForegroundColor Green
    Deploy "addon\apps\ladepreis_graph.py" "$HA_ADDON_APPS/ladepreis_graph.py"
    Deploy "addon\apps\ladeSession.py"     "$HA_ADDON_APPS/ladeSession.py"
}

Write-Host "`nFertig." -ForegroundColor Green
