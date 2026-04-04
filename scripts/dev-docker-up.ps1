# Arrête les conteneurs expensevoice existants (conflits noms/ports), puis lance le stack dev.
# Usage: .\scripts\dev-docker-up.ps1
# Depuis la racine du repo: .\scripts\dev-docker-up.ps1

$ErrorActionPreference = "Stop"
# Racine du repo (parent du dossier scripts)
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$containers = @("expensevoice_frontend", "expensevoice_backend", "expensevoice_db")
foreach ($c in $containers) {
    $exists = docker ps -a -q -f "name=^${c}$" 2>$null
    if ($exists) {
        Write-Host "Arrêt et suppression de $c..."
        docker stop $c 2>$null
        docker rm $c 2>$null
    }
}

# Une seule stack à la fois : backend = 8000. Arrêt stack principale (abes_dev_*, docker-compose.yml).
Write-Host "Arrêt du stack principal expensevoice-ai (docker-compose.yml) s'il tourne..."
docker compose down 2>&1 | Out-Null
$LASTEXITCODE = 0

# Ancien nom de projet Compose + projet défini par name: dans docker-compose.dev.yml
Write-Host "Arrêt des stacks docker-compose.dev.yml (expensevoice-dev / expensevoice-ai-dev)..."
docker compose -f docker-compose.dev.yml -p expensevoice-dev down 2>&1 | Out-Null
docker compose -f docker-compose.dev.yml down 2>&1 | Out-Null
$LASTEXITCODE = 0

# Arrêter aussi le stack infra s'il tourne (même conteneurs)
$infraPath = Join-Path $root "infra\docker-compose.yml"
if (Test-Path $infraPath) {
    Write-Host "Arrêt du stack infra (s'il tourne)..."
    docker compose -f $infraPath down 2>&1 | Out-Null
    $LASTEXITCODE = 0
}

Write-Host "Lancement du stack expensevoice-ai-dev (docker-compose.dev.yml)..."
docker compose -f docker-compose.dev.yml up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "OK. Frontend: http://localhost:3000  |  Backend: http://localhost:8000"
