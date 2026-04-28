# Synchronise mobile/.env (API) avec l'IPv4 LAN du PC (route par defaut, hors vEthernet/WSL/VPN).
# Usage (depuis mobile/) :
#   .\scripts\sync-iphone-lan.ps1
#   .\scripts\sync-iphone-lan.ps1 -Ip 192.168.1.10   # forcer une IP (hotspot change, etc.)
#   .\scripts\sync-iphone-lan.ps1 -Start             # sync puis lance Expo en --lan
param(
    [switch]$Start,
    [string]$Ip = ""
)

$ErrorActionPreference = "Stop"
$mobileRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$envFile = Join-Path $mobileRoot ".env"
$apiPort = 8000

function Get-DefaultRouteIPv4 {
    $skip = "vEthernet|Hyper-V|WSL|VirtualBox|VMware|Tailscale|ZeroTier|TAP-Windows|TUN|VPN"
    $routes = Get-NetRoute -AddressFamily IPv4 -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Sort-Object RouteMetric
    foreach ($r in $routes) {
        $ad = Get-NetAdapter -InterfaceIndex $r.InterfaceIndex -ErrorAction SilentlyContinue
        if (-not $ad -or $ad.Status -ne "Up") { continue }
        if ($ad.Name -match $skip) { continue }
        $ip = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $r.InterfaceIndex -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notmatch "^127\." -and $_.IPAddress -notmatch "^169\.254\." } |
            Select-Object -ExpandProperty IPAddress -First 1
        if ($ip) { return $ip }
    }
    foreach ($r in $routes) {
        $ip = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $r.InterfaceIndex -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notmatch "^127\." -and $_.IPAddress -notmatch "^169\.254\." } |
            Select-Object -ExpandProperty IPAddress -First 1
        if ($ip) { return $ip }
    }
    throw "Impossible de trouver une IPv4 LAN (route 0.0.0.0/0). Verifiez Wi-Fi / Ethernet."
}

if ($Ip) {
    $lanIp = $Ip.Trim()
} else {
    $lanIp = Get-DefaultRouteIPv4
}
$newLine = "EXPO_PUBLIC_API_URL=http://${lanIp}:${apiPort}"

$utf8 = New-Object System.Text.UTF8Encoding $false
if (-not (Test-Path $envFile)) {
    [System.IO.File]::WriteAllLines($envFile, @(
        "# Sync API + iPhone: npm run sync:lan",
        $newLine,
        ""
    ), $utf8)
    Write-Host "Créé $envFile"
} else {
    $lines = Get-Content -Path $envFile
    $replaced = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*EXPO_PUBLIC_API_URL=") {
            $replaced = $true
            $newLine
        } else {
            $line
        }
    }
    if (-not $replaced) {
        $out = @($out) + $newLine
    }
    [System.IO.File]::WriteAllLines($envFile, [string[]]@($out), $utf8)
    Write-Host "Mis à jour $envFile"
}

Write-Host ""
Write-Host "LAN IPv4 détectée : $lanIp"
Write-Host "API mobile       : $newLine"
Write-Host "Metro (Expo Go)  : exp://${lanIp}:8081"
Write-Host ""

if ($Start) {
    Set-Location $mobileRoot
    $env:REACT_NATIVE_PACKAGER_HOSTNAME = $lanIp
    Write-Host "Démarrage Expo (--lan)..."
    npx expo start --lan --clear
} else {
    Write-Host "Ensuite, dans ce dossier mobile :"
    Write-Host ('  $env:REACT_NATIVE_PACKAGER_HOSTNAME="{0}"; npx expo start --lan --clear' -f $lanIp)
    Write-Host ""
    Write-Host "Ou en une ligne : npm run start:iphone"
}
