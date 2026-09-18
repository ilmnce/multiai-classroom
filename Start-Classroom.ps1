param(
    [Parameter(Position = 0)]
    [string]$Project = $PSScriptRoot,

    [Parameter(Position = 1)]
    [string]$Prompt,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) {
    throw "OpenCode CLI tidak ditemukan di PATH."
}

if (-not (Get-Command omniroute -ErrorAction SilentlyContinue)) {
    throw "OmniRoute CLI tidak ditemukan di PATH."
}

if (-not (Test-Path -LiteralPath $Project -PathType Container)) {
    throw "Folder proyek tidak ditemukan: $Project"
}

$authScript = Join-Path (Split-Path $PSScriptRoot -Parent) "codex-freemium\auth.ps1"
if (-not (Test-Path -LiteralPath $authScript -PathType Leaf)) {
    throw "Penyimpanan key OmniRoute terenkripsi tidak ditemukan."
}

$healthy = $false
try {
    $probe = Invoke-RestMethod -Uri "http://127.0.0.1:20128/healthz" -TimeoutSec 3
    $healthy = (($probe -is [string]) -and $probe.Trim() -eq "ok") -or $probe.status -eq "healthy"
} catch {}

if (-not $healthy) {
    & omniroute serve --daemon --no-open --no-tray | Out-Null
    for ($attempt = 0; $attempt -lt 15; $attempt += 1) {
        Start-Sleep -Seconds 1
        try {
            $probe = Invoke-RestMethod -Uri "http://127.0.0.1:20128/healthz" -TimeoutSec 3
            if ((($probe -is [string]) -and $probe.Trim() -eq "ok") -or $probe.status -eq "healthy") {
                $healthy = $true
                break
            }
        } catch {}
    }
}

if (-not $healthy) {
    throw "OmniRoute belum sehat di port 20128."
}

$previousKey = $env:OMNIROUTE_API_KEY
$previousClaudeFlag = $env:OPENCODE_DISABLE_CLAUDE_CODE
$previousConfig = $env:OPENCODE_CONFIG
$previousConfigDir = $env:OPENCODE_CONFIG_DIR

try {
    $env:OMNIROUTE_API_KEY = & $authScript
    if (-not $env:OMNIROUTE_API_KEY) {
        throw "Key OmniRoute tidak tersedia."
    }
    $env:OPENCODE_DISABLE_CLAUDE_CODE = "1"
    $env:OPENCODE_CONFIG = Join-Path $PSScriptRoot "opencode.jsonc"
    $env:OPENCODE_CONFIG_DIR = Join-Path $PSScriptRoot ".opencode"

    if ($Prompt) {
        $format = if ($Json) { "json" } else { "default" }
        & opencode run --dir $Project --agent teacher --format $format $Prompt
    } else {
        & opencode $Project --agent teacher
    }

    if ($LASTEXITCODE -ne 0) {
        throw "OpenCode keluar dengan code $LASTEXITCODE."
    }
} finally {
    if ($null -eq $previousKey) {
        Remove-Item Env:OMNIROUTE_API_KEY -ErrorAction SilentlyContinue
    } else {
        $env:OMNIROUTE_API_KEY = $previousKey
    }

    if ($null -eq $previousClaudeFlag) {
        Remove-Item Env:OPENCODE_DISABLE_CLAUDE_CODE -ErrorAction SilentlyContinue
    } else {
        $env:OPENCODE_DISABLE_CLAUDE_CODE = $previousClaudeFlag
    }

    if ($null -eq $previousConfig) {
        Remove-Item Env:OPENCODE_CONFIG -ErrorAction SilentlyContinue
    } else {
        $env:OPENCODE_CONFIG = $previousConfig
    }

    if ($null -eq $previousConfigDir) {
        Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue
    } else {
        $env:OPENCODE_CONFIG_DIR = $previousConfigDir
    }
}
