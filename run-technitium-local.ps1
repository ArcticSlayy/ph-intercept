$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$envFile = Join-Path $repoRoot ".env"
if (Test-Path -LiteralPath $envFile) {
    Get-Content -LiteralPath $envFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
        $name, $value = $line.Split("=", 2)
        $name = $name.Trim()
        if (-not $name -or [Environment]::GetEnvironmentVariable($name, "Process")) { return }
        $value = $value.Trim()
        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

$env:PROVIDER = "technitium"
$env:TECHNITIUM_DASHBOARD = if ($env:TECHNITIUM_DASHBOARD) { $env:TECHNITIUM_DASHBOARD } else { "http://127.0.0.1:5380" }
$env:TECHNITIUM_API_URL = if ($env:TECHNITIUM_API_URL) { $env:TECHNITIUM_API_URL } else { $env:TECHNITIUM_DASHBOARD }
$env:TECHNITIUM_API_QUERY_LOG_NAME = if ($env:TECHNITIUM_API_QUERY_LOG_NAME) { $env:TECHNITIUM_API_QUERY_LOG_NAME } else { "Query Logs (Sqlite)" }
$env:TECHNITIUM_API_QUERY_LOG_CLASS_PATH = if ($env:TECHNITIUM_API_QUERY_LOG_CLASS_PATH) { $env:TECHNITIUM_API_QUERY_LOG_CLASS_PATH } else { "QueryLogsSqlite.App" }
$env:TECHNITIUM_API_STATS_TYPE = if ($env:TECHNITIUM_API_STATS_TYPE) { $env:TECHNITIUM_API_STATS_TYPE } else { "LastDay" }
$env:TECHNITIUM_API_ENTRIES_PER_PAGE = if ($env:TECHNITIUM_API_ENTRIES_PER_PAGE) { $env:TECHNITIUM_API_ENTRIES_PER_PAGE } else { "50" }
$env:TECHNITIUM_API_POLL_SECONDS = if ($env:TECHNITIUM_API_POLL_SECONDS) { $env:TECHNITIUM_API_POLL_SECONDS } else { "1.0" }
$env:TECHNITIUM_API_ALLOW_CONTROL = if ($env:TECHNITIUM_API_ALLOW_CONTROL) { $env:TECHNITIUM_API_ALLOW_CONTROL } else { "false" }
$env:TECHNITIUM_REPLAY_RECENT = if ($env:TECHNITIUM_REPLAY_RECENT) { $env:TECHNITIUM_REPLAY_RECENT } else { "20" }
$env:TECHNITIUM_REPLAY_MAX_AGE_SECONDS = if ($env:TECHNITIUM_REPLAY_MAX_AGE_SECONDS) { $env:TECHNITIUM_REPLAY_MAX_AGE_SECONDS } else { "120" }
$env:RETURN_URL = if ($env:RETURN_URL) { $env:RETURN_URL } else { "http://127.0.0.1:5380" }
$env:BG_MODE = if ($env:BG_MODE) { $env:BG_MODE } else { "starfield" }
$env:SKY_PRESET = if ($env:SKY_PRESET) { $env:SKY_PRESET } else { "summer_triangle" }
$hostAddress = if ($env:PH_INTERCEPT_HOST) { $env:PH_INTERCEPT_HOST } else { "127.0.0.1" }
$port = if ($env:PH_INTERCEPT_PORT) { $env:PH_INTERCEPT_PORT } else { "4653" }

if (-not (Test-Path -LiteralPath ".\.venv\Scripts\python.exe")) {
    py -3 -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not $env:TECHNITIUM_API_TOKEN -and -not ($env:TECHNITIUM_API_USER -and $env:TECHNITIUM_API_PASSWORD)) {
    Write-Warning "Set TECHNITIUM_API_TOKEN, or TECHNITIUM_API_USER and TECHNITIUM_API_PASSWORD, for live Technitium API data."
}
Write-Host "Starting Technitium ph-intercept at http://$hostAddress`:$port"
Write-Host "Technitium's normal UI stays at http://127.0.0.1:5380"
Write-Host "Press Ctrl+C in this window to stop ph-intercept."
.\.venv\Scripts\python.exe -m uvicorn app:app --host $hostAddress --port $port
