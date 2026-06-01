param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $DbtArgs
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ProjectDir
$DuckHome = Join-Path $ProjectDir ".duckdb_home"
$LogPath = Join-Path $DuckHome "logs"
$EnvFile = Join-Path $RepoDir ".env"
$VenvDbt = Join-Path $RepoDir ".venv\Scripts\dbt.exe"

New-Item -ItemType Directory -Force $DuckHome | Out-Null
New-Item -ItemType Directory -Force $LogPath | Out-Null
$env:USERPROFILE = $DuckHome
$env:HOME = $DuckHome
$env:DUCKDB_HOME = $DuckHome

if (Test-Path $EnvFile) {
    Get-Content $EnvFile |
        Where-Object { $_ -match '^[A-Za-z_][A-Za-z0-9_]*=' } |
        ForEach-Object {
            $parts = $_ -split '=', 2
            Set-Item -Path "env:$($parts[0])" -Value $parts[1]
        }
}

if (Test-Path $VenvDbt) {
    & $VenvDbt @DbtArgs --project-dir $ProjectDir --profiles-dir $ProjectDir --log-path $LogPath
} else {
    & dbt @DbtArgs --project-dir $ProjectDir --profiles-dir $ProjectDir --log-path $LogPath
}
