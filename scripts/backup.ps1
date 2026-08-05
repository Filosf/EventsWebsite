$ErrorActionPreference = "Stop"

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$env:BACKUP_NAME = "wedding-events_$stamp"
try {
    docker-compose --profile tools run --rm backup
    if ($LASTEXITCODE -ne 0) {
        throw "Backup failed with exit code $LASTEXITCODE."
    }
    Write-Host "Backup created in backups/$($env:BACKUP_NAME)-*"
}
finally {
    Remove-Item Env:BACKUP_NAME -ErrorAction SilentlyContinue
}
