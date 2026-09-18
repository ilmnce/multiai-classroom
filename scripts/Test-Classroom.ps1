param([switch]$Live)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $PSScriptRoot -Parent
$requiredAgents = @(
    "teacher",
    "student-architect",
    "student-builder",
    "student-verifier",
    "student-cleanup",
    "student-documenter"
)

$probe = Invoke-RestMethod -Uri "http://127.0.0.1:20128/healthz" -TimeoutSec 5
if (-not ((($probe -is [string]) -and $probe.Trim() -eq "ok") -or $probe.status -eq "healthy")) {
    throw "OmniRoute health check gagal."
}

$previousConfig = $env:OPENCODE_CONFIG
$previousConfigDir = $env:OPENCODE_CONFIG_DIR
$env:OPENCODE_CONFIG = Join-Path $projectRoot "opencode.jsonc"
$env:OPENCODE_CONFIG_DIR = Join-Path $projectRoot ".opencode"

Push-Location (Join-Path $projectRoot "work")
try {
    $agentList = (& opencode agent list 2>&1) -join "`n"
    foreach ($agent in $requiredAgents) {
        if ($agentList -notmatch "(?m)^$([regex]::Escape($agent)) \(") {
            throw "Agent tidak ditemukan oleh OpenCode: $agent"
        }
    }
} finally {
    Pop-Location
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

$authScript = Join-Path (Split-Path $projectRoot -Parent) "codex-freemium\auth.ps1"
$previousKey = $env:OMNIROUTE_API_KEY
try {
    $env:OMNIROUTE_API_KEY = & $authScript
    $headers = @{ Authorization = "Bearer $env:OMNIROUTE_API_KEY" }

    foreach ($case in @(
        @{ Model = "freemium"; Marker = "TEACHER_SMOKE_OK" },
        @{ Model = "classroom-students"; Marker = "STUDENT_SMOKE_OK" }
    )) {
        $body = @{
            model = $case.Model
            messages = @(@{ role = "user"; content = "Reply with exactly $($case.Marker)" })
            max_tokens = 40
            temperature = 0
        } | ConvertTo-Json -Depth 6

        $response = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:20128/v1/chat/completions" -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 120
        if ($response.choices[0].message.content -notmatch [regex]::Escape($case.Marker)) {
            throw "Route $($case.Model) tidak mengembalikan marker yang diharapkan."
        }
    }
} finally {
    if ($null -eq $previousKey) {
        Remove-Item Env:OMNIROUTE_API_KEY -ErrorAction SilentlyContinue
    } else {
        $env:OMNIROUTE_API_KEY = $previousKey
    }
}

Write-Output "CLASSROOM_STATIC_SMOKE_OK"

if ($Live) {
    $prompt = @"
Run the orchestration smoke test only. Call student-architect, student-builder, student-verifier, student-cleanup, and student-documenter exactly once in that dependency order. Forward every returned marker to the next Student. Do not edit files and do not run shell commands. Independently confirm the complete chain, then return CLASSROOM_E2E_OK only after all five task calls succeed.
"@
    & (Join-Path $projectRoot "Start-Classroom.ps1") -Project $projectRoot -Prompt $prompt
}
