$HA_HOST   = "192.168.198.25"
$HA_USER   = "root"
$ADDON_DIR = "/addons/nachbarschaft-laden"
# Nach Code-Aenderungen: git push, dann .\deploy.ps1 [addon|hotdeploy]
# Das Skript loest store-reload + rebuild via HA-API aus.

function Deploy($local, $remote) {
    Write-Host "  $local" -ForegroundColor Cyan
    scp $local "${HA_USER}@${HA_HOST}:${remote}"
    if ($LASTEXITCODE -ne 0) { Write-Error "Fehler bei: $local"; exit 1 }
}

function RunSsh($cmd) {
    & ssh "${HA_USER}@${HA_HOST}" $cmd
    if ($LASTEXITCODE -ne 0) { Write-Error "SSH-Fehler: $cmd"; exit 1 }
}

# Auswahl
$target = $args[0]
if (-not $target) { $target = "addon" }

# Add-on deployen (lokale Dateien -> HA Supervisor)
# Setzt voraus: git push wurde vorher ausgefuehrt.
if ($target -eq "addon") {
    Write-Host "`nDeploy Add-on (lokale Dateien -> HA)" -ForegroundColor Green

    Deploy "addon\config.yaml"    "$ADDON_DIR/config.yaml"
    Deploy "addon\CHANGELOG.md"   "$ADDON_DIR/CHANGELOG.md"
    Deploy "addon\run.sh"         "$ADDON_DIR/run.sh"
    Deploy "addon\Dockerfile"     "$ADDON_DIR/Dockerfile"

    # www/ und apps/ hochladen (werden beim Rebuild ins Image kopiert)
    RunSsh "mkdir -p $ADDON_DIR/www $ADDON_DIR/apps"
    Get-ChildItem "addon\www" | ForEach-Object {
        Deploy "addon\www\$($_.Name)" "$ADDON_DIR/www/$($_.Name)"
    }
    Get-ChildItem "addon\apps" -Filter "*.py" | ForEach-Object {
        Deploy "addon\apps\$($_.Name)" "$ADDON_DIR/apps/$($_.Name)"
    }

    Write-Host "  Supervisor Store reload..." -ForegroundColor Cyan
    $storeResult = & ssh "${HA_USER}@${HA_HOST}" 'curl -sf -X POST -H "Authorization: Bearer $SUPERVISOR_TOKEN" http://supervisor/store/reload'
    if ($LASTEXITCODE -ne 0) { Write-Warning "store/reload fehlgeschlagen: $storeResult" }

    $info    = & ssh "${HA_USER}@${HA_HOST}" "ha apps info local_nachbarschaft_laden 2>/dev/null"
    $version = ($info | Select-String 'version:'        | Select-Object -First 1).Line.Split(':')[1].Trim()
    $latest  = ($info | Select-String 'version_latest:' | Select-Object -First 1).Line.Split(':')[1].Trim()
    Write-Host "  Installiert: $version  |  Verfuegbar: $latest" -ForegroundColor Cyan

    if ($version -ne $latest) {
        Write-Host "  Starte Update auf $latest ..." -ForegroundColor Cyan
        RunSsh "ha apps update local_nachbarschaft_laden 2>&1"
    } else {
        Write-Host "  Gleiche Version - fuehre Rebuild durch ..." -ForegroundColor Cyan
        RunSsh "ha apps rebuild local_nachbarschaft_laden 2>&1"
    }
    Write-Host "  Add-on aktualisiert. Logs: ha apps logs local_nachbarschaft_laden" -ForegroundColor Cyan
}

# Hot-Deploy Python Apps (kein Docker-Rebuild noetig)
# AppDaemon laedt geaenderte .py Dateien automatisch neu.
$HA_ADDON_APPS = "/homeassistant/.addon_nachbarschaft_laden/apps"
if ($target -eq "hotdeploy") {
    Write-Host "`nHot-Deploy Python Apps" -ForegroundColor Green
    Deploy "addon\apps\ladepreis_graph.py" "$HA_ADDON_APPS/ladepreis_graph.py"
    Deploy "addon\apps\ladeSession.py"     "$HA_ADDON_APPS/ladeSession.py"
}

Write-Host "`nFertig." -ForegroundColor Green
