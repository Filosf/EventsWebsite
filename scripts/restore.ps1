param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_.-]+$')]
    [string]$BackupName,

    [Parameter(Mandatory = $true)]
    [switch]$IUnderstandThisWillOverwriteData
)

$ErrorActionPreference = "Stop"
$backupRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\backups")).Path
$databaseBackup = Join-Path $backupRoot "$BackupName-db.dump"
$mediaBackup = Join-Path $backupRoot "$BackupName-media.tar.gz"
$checksumFile = Join-Path $backupRoot "$BackupName.sha256"
if (
    -not (Test-Path -LiteralPath $databaseBackup) -or
    -not (Test-Path -LiteralPath $mediaBackup) -or
    -not (Test-Path -LiteralPath $checksumFile)
) {
    throw "Backup files were not found inside $backupRoot."
}

$env:BACKUP_NAME = $BackupName
$env:RESTORE_CONFIRM = "YES"
try {
    docker-compose stop proxy web
    if ($LASTEXITCODE -ne 0) { throw "Could not stop application services." }
    docker-compose --profile tools run --rm restore
    if ($LASTEXITCODE -ne 0) { throw "Restore failed with exit code $LASTEXITCODE." }
    docker-compose up -d web proxy
    if ($LASTEXITCODE -ne 0) { throw "Restore completed, but application services did not start." }
}
finally {
    Remove-Item Env:BACKUP_NAME -ErrorAction SilentlyContinue
    Remove-Item Env:RESTORE_CONFIRM -ErrorAction SilentlyContinue
}
