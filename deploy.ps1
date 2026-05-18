$HA_HOST     = "<HA-IP-ADRESSE>"
$HA_USER     = "root"
$AD_APPS     = "/addon_configs/a0d7b954_appdaemon/apps"
$HA_WWW      = "/homeassistant/www/nachbarschaft-laden"
$ADDON_DIR   = "/addons/nachbarschaft-laden"
# HINWEIS: Das Add-on wird aus dem GitHub-Repo gebaut (bernd780/Nachbarschaft-Laden).
# Nach Code-Ã„nderungen: git push, dann .\deploy.ps1 addon
# Das Skript lÃ¶st store-reload + update via HA-API aus.

function Deploy($local, $remote) {
    Write-Host "  $local" -ForegroundColor Cyan
    scp $local "${HA_USER}@${HA_HOST}:${remote}"
    if ($LASTEXITCODE -ne 0) { Write-Error "Fehler bei: $local"; exit 1 }
}

function RunSsh($cmd) {
    & ssh "${HA_USER}@${HA_HOST}" $cmd
    if ($LASTEXITCODE -ne 0) { Write-Error "SSH-Fehler: $cmd"; exit 1 }
}

# â”€â”€ Auswahl â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$target = $args[0]
if (-not $target) { $target = "all" }

# â”€â”€ Add-on deployen (GitHub â†’ HA Supervisor) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Das Add-on wird aus dem GitHub-Repo bernd780/Nachbarschaft-Laden gebaut.
# Zuerst git push, dann dieses Skript aufrufen.
if ($target -in "all", "addon") {
    Write-Host "`nDeploy Add-on (via GitHub + HA Supervisor)" -ForegroundColor Green

    # 1. Supervisor Store neu laden (git pull von GitHub)
    Write-Host "  Supervisor Store reload..." -ForegroundColor Cyan
    $storeResult = & ssh "${HA_USER}@${HA_HOST}" "curl -sf -X POST -H 'Authorization: Bearer \$SUPERVISOR_TOKEN' http://supervisor/store/reload"
    if ($LASTEXITCODE -ne 0) { Write-Warning "store/reload fehlgeschlagen: $storeResult" }

    # 2. PrÃ¼fen ob Update oder Rebuild nÃ¶tig
    $info = & ssh "${HA_USER}@${HA_HOST}" "ha apps info 41bf84da_nachbarschaft_laden 2>/dev/null"
    $version = ($info | Select-String 'version:' | Select-Object -First 1).Line.Split(':')[1].Trim()
    $latest  = ($info | Select-String 'version_latest:' | Select-Object -First 1).Line.Split(':')[1].Trim()
    Write-Host "  Installiert: $version  |  VerfÃ¼gbar: $latest" -ForegroundColor Cyan

    if ($version -ne $latest) {
        Write-Host "  Starte Update auf $latest ..." -ForegroundColor Cyan
        RunSsh "ha apps update 41bf84da_nachbarschaft_laden 2>&1"
    } else {
        Write-Host "  Gleiche Version â€“ fÃ¼hre Rebuild durch ..." -ForegroundColor Cyan
        RunSsh "ha apps rebuild 41bf84da_nachbarschaft_laden 2>&1"
    }
    Write-Host "  Add-on aktualisiert. Logs: ha apps logs 41bf84da_nachbarschaft_laden" -ForegroundColor Cyan
}

# â”€â”€ AppDaemon Apps hot-deploy (neues Add-on, kein Docker-Rebuild nÃ¶tig) â”€â”€â”€â”€â”€â”€
# APPS_DIR=/homeassistant/.addon_nachbarschaft_laden/apps ist bind-gemountet.
# AppDaemon lÃ¤dt geÃ¤nderte .py Dateien automatisch neu.
$HA_ADDON_APPS = "/homeassistant/.addon_nachbarschaft_laden/apps"
if ($target -in "hotdeploy") {
    Write-Host "`nHot-Deploy Python Apps ins neue Add-on" -ForegroundColor Green
    Deploy "addon\apps\ladepreis_graph.py" "$HA_ADDON_APPS/ladepreis_graph.py"
    Deploy "addon\apps\ladeSession.py"     "$HA_ADDON_APPS/ladeSession.py"
}

# â”€â”€ AppDaemon Apps deployen (legacy standalone AppDaemon) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if ($target -in "all", "appdaemon") {
    Write-Host "`nDeploy AppDaemon Apps (legacy)" -ForegroundColor Green
    Deploy "appdeamon\ladeSession.py"     "$AD_APPS/ladeSession.py"
    Deploy "appdeamon\ladepreis_graph.py" "$AD_APPS/ladepreis_graph.py"
    Deploy "appdeamon\apps.yaml"          "$AD_APPS/apps.yaml"
}

# â”€â”€ Web-Frontend deployen â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if ($target -in "all", "www") {
    Write-Host "`nDeploy Web-Frontend" -ForegroundColor Green
    Deploy "www\index.html"                   "$HA_WWW/index.html"
    Deploy "www\sessions.html"                "$HA_WWW/sessions.html"
    Deploy "www\rechner.html"                 "$HA_WWW/rechner.html"
    Deploy "www\display_preview_viewer.html"  "$HA_WWW/display_preview_viewer.html"
    Deploy "www\display.html"                 "$HA_WWW/display.html"
}

Write-Host "`nFertig." -ForegroundColor Green
