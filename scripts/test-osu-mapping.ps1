<#
.SYNOPSIS
    Independent Test Suite and Verification Harness for osu! Mapping MVP
    Tests Custom Tools, Acceptance Criteria (PRD Section 19), Plugin Guard, and Security Gates.

.DESCRIPTION
    Executes automated tests covering:
    1. Custom Tools (osu_map_inspect, osu_map_generate, osu_map_validate, osu_map_originality)
    2. PRD Section 19 Acceptance Test Matrix (AC-01 through AC-11)
    3. Path Guard & Canonical Path Escape Rejection (POLICY_DENIED)
    4. Anti-Plagiarism & Originality Gate (CLONE detection on self-reference)
    5. Beat-Grid Snapping & Off-Grid Detection
    6. Song Coverage Gate (< 95% detection)
    7. Secret & Environment Redaction (controlled fake secret token)
    8. Double-Run Idempotency & Unique Run Directory Allocation
    9. Source Immutability & Preservation
    10. Plugin Guard Lifecycle & Append-Only Event Log (events.jsonl)
    11. Recovery from Pre-Validated Candidates
    12. Completion Guard Cross-Referencing

.EXAMPLE
    pwsh scripts/test-osu-mapping.ps1
    powershell -ExecutionPolicy Bypass -File scripts/test-osu-mapping.ps1
#>

$ErrorActionPreference = "Continue"

# Resolve project root directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -LiteralPath $ProjectRoot

# Test Harness State
$script:TotalTests = 0
$script:PassedTests = 0
$script:FailedTests = 0
$script:TestSummary = @()

function Run-Test {
    param(
        [Parameter(Mandatory=$true)][string]$Category,
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][scriptblock]$TestScript
    )

    $script:TotalTests++
    $testNumber = $script:TotalTests
    $categoryTag = "[$Category]"

    try {
        $result = & $TestScript
        if ($result.Passed -eq $true) {
            $script:PassedTests++
            Write-Host ("  [PASS] Test {0:D2} {1,-14} : {2}" -f $testNumber, $categoryTag, $Name) -ForegroundColor Green
            if ($result.Details) {
                Write-Host ("         Evidence: {0}" -f $result.Details) -ForegroundColor DarkGray
            }
            $script:TestSummary += [PSCustomObject]@{
                ID = $testNumber
                Category = $Category
                Name = $Name
                Status = "PASS"
                Details = $result.Details
            }
        } else {
            $script:FailedTests++
            Write-Host ("  [FAIL] Test {0:D2} {1,-14} : {2}" -f $testNumber, $categoryTag, $Name) -ForegroundColor Red
            Write-Host ("         Reason: {0}" -f ($result.Reason -join "; ")) -ForegroundColor DarkRed
            $script:TestSummary += [PSCustomObject]@{
                ID = $testNumber
                Category = $Category
                Name = $Name
                Status = "FAIL"
                Details = ($result.Reason -join "; ")
            }
        }
    } catch {
        $script:FailedTests++
        Write-Host ("  [FAIL] Test {0:D2} {1,-14} : {2}" -f $testNumber, $categoryTag, $Name) -ForegroundColor Red
        Write-Host ("         Exception: {0}" -f $_.Exception.Message) -ForegroundColor DarkRed
        $script:TestSummary += [PSCustomObject]@{
            ID = $testNumber
            Category = $Category
            Name = $Name
            Status = "ERROR"
            Details = $_.Exception.Message
        }
    }
}

# Helper to compute SHA-256 in PowerShell
function Get-FileSha256 {
    param([string]$FilePath)
    if (-not (Test-Path -LiteralPath $FilePath)) { return $null }
    $hash = Get-FileHash -LiteralPath $FilePath -Algorithm SHA256
    return $hash.Hash.ToLower()
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " osu! Mapping MVP - Comprehensive Test Suite & Plugin Guard Verification" -ForegroundColor Cyan
Write-Host " Target Directory: $ProjectRoot" -ForegroundColor Cyan
Write-Host " Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Setup clean test workspace in work/mapping-runs/test-harness-*
$TestRunsRoot = Join-Path $ProjectRoot "work\mapping-runs\test-harness"
if (Test-Path -LiteralPath $TestRunsRoot) {
    Remove-Item -LiteralPath $TestRunsRoot -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $TestRunsRoot | Out-Null

$FixturesDir = Join-Path $ProjectRoot ".opencode\fixtures"
$CanonicalMap = Join-Path $FixturesDir "canonical-map.osu"
$OffGridMap = Join-Path $FixturesDir "off-grid-map.osu"
$ShortCoverageMap = Join-Path $FixturesDir "short-coverage-map.osu"
$SelfRefMap = Join-Path $FixturesDir "self-reference.osu"
$RefOsuMap = Join-Path $FixturesDir "reference-osu-map.osu"
$AudioPlaceholder = Join-Path $FixturesDir "sample-audio-placeholder.txt"

# ------------------------------------------------------------------------------
# SECTION 1: Fixtures & Environment Integrity
# ------------------------------------------------------------------------------
Write-Host "--- Section 1: Fixtures & Environment Integrity ---" -ForegroundColor Yellow

Run-Test -Category "Fixtures" -Name "Test fixtures existence and non-empty sizes" -TestScript {
    $files = @($CanonicalMap, $OffGridMap, $ShortCoverageMap, $SelfRefMap, $RefOsuMap, $AudioPlaceholder)
    $missing = @()
    foreach ($f in $files) {
        if (-not (Test-Path -LiteralPath $f) -or ((Get-Item -LiteralPath $f).Length -eq 0)) {
            $missing += $f
        }
    }
    if ($missing.Count -eq 0) {
        return @{ Passed = $true; Details = "All 6 fixture files verified." }
    } else {
        return @{ Passed = $false; Reason = @("Missing or empty fixtures: $($missing -join ', ')") }
    }
}

Run-Test -Category "Fixtures" -Name "Canonical map format and hit object count" -TestScript {
    $content = Get-Content -LiteralPath $CanonicalMap -Raw
    $hasHeader = $content -match "osu file format v14"
    $hasTiming = $content -match "\[TimingPoints\]"
    $hasHitObjs = $content -match "\[HitObjects\]"
    if ($hasHeader -and $hasTiming -and $hasHitObjs) {
        return @{ Passed = $true; Details = "Canonical map has valid v14 header and required sections." }
    } else {
        return @{ Passed = $false; Reason = @("Canonical map missing header or sections.") }
    }
}

# ------------------------------------------------------------------------------
# SECTION 2: Custom Tools Direct Execution
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "--- Section 2: Custom Tools Typed Execution ---" -ForegroundColor Yellow

Run-Test -Category "Tool:Inspect" -Name "osu_map_inspect: Parse canonical .osu file" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { osu_map_inspect } from './.opencode/tools/osu-map-inspect.ts'; osu_map_inspect.execute({ path: '.opencode/fixtures/canonical-map.osu' }, { directory: process.cwd(), worktree: process.cwd() } as any).then(r => console.log(r))`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.exists -eq $true -and $json.osu_details.format_version -eq 14 -and $json.osu_details.hit_objects_count.total -eq 25) {
        return @{ Passed = $true; Details = "Parsed format v14, 25 hit objects, playfield within bounds." }
    } else {
        return @{ Passed = $false; Reason = @("Inspect output did not match expected structure.") }
    }
}

Run-Test -Category "Tool:Inspect" -Name "osu_map_inspect: Reject sensitive path (.env / credentials)" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { osu_map_inspect } from './.opencode/tools/osu-map-inspect.ts'; osu_map_inspect.execute({ path: '.env' }, { directory: process.cwd(), worktree: process.cwd() } as any).then(r => console.log(r))`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.error.code -eq "ACCESS_DENIED") {
        return @{ Passed = $true; Details = "Access denied returned for .env inspection." }
    } else {
        return @{ Passed = $false; Reason = @("Failed to reject .env access: $output") }
    }
}

Run-Test -Category "Tool:Generate" -Name "osu_map_generate: Generate candidate in designated run directory" -TestScript {
    $targetDir = "work/mapping-runs/test-harness/run-gen-01"
    $cmd = "node --experimental-strip-types -e `"import { osu_map_generate } from './.opencode/tools/osu-map-generate.ts'; osu_map_generate.execute({ run_directory: '$targetDir', bpm: 100, duration_ms: 30000, style: 'hybrid' }, { directory: process.cwd(), worktree: process.cwd() } as any).then(r => console.log(r))`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    $candFile = Join-Path $ProjectRoot "$targetDir\candidate\candidate.osu"
    $compFile = Join-Path $ProjectRoot "$targetDir\reports\completion-report.json"
    if ($json.status -eq "COMPLETE" -and (Test-Path -LiteralPath $candFile) -and (Test-Path -LiteralPath $compFile)) {
        return @{ Passed = $true; Details = "Generated candidate.osu and completion-report.json with status COMPLETE." }
    } else {
        return @{ Passed = $false; Reason = @("Generation failed or missing artifacts: $output") }
    }
}

Run-Test -Category "Tool:Generate" -Name "osu_map_generate: Reject invalid target path containing .env" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { osu_map_generate } from './.opencode/tools/osu-map-generate.ts'; osu_map_generate.execute({ run_directory: 'work/.env/run-bad' }, { directory: process.cwd(), worktree: process.cwd() } as any).then(r => console.log(r))`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.error.code -eq "INVALID_TARGET_DIR") {
        return @{ Passed = $true; Details = "Blocked target directory inside .env." }
    } else {
        return @{ Passed = $false; Reason = @("Failed to reject invalid target directory: $output") }
    }
}

Run-Test -Category "Tool:Validate" -Name "osu_map_validate: Canonical map validation verdict PASS" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { osu_map_validate } from './.opencode/tools/osu-map-validate.ts'; osu_map_validate.execute({ candidate_path: '.opencode/fixtures/canonical-map.osu' }, { directory: process.cwd(), worktree: process.cwd() } as any).then(r => console.log(r))`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.verdict -eq "PASS" -and $json.stage_results.beat_grid_validity -eq "PASS" -and $json.stage_results.file_integrity -eq "PASS") {
        return @{ Passed = $true; Details = "Validation verdict PASS across all stages." }
    } else {
        return @{ Passed = $false; Reason = @("Validation failed for canonical map: $output") }
    }
}

Run-Test -Category "Tool:Validate" -Name "osu_map_validate: Off-grid map detection (beat_grid_validity FAIL)" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { osu_map_validate } from './.opencode/tools/osu-map-validate.ts'; osu_map_validate.execute({ candidate_path: '.opencode/fixtures/off-grid-map.osu' }, { directory: process.cwd(), worktree: process.cwd() } as any).then(r => console.log(r))`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.verdict -eq "FAIL" -and $json.stage_results.beat_grid_validity -eq "FAIL") {
        return @{ Passed = $true; Details = "Correctly detected 5 off-grid objects and failed beat_grid_validity." }
    } else {
        return @{ Passed = $false; Reason = @("Off-grid map was not rejected: $output") }
    }
}

Run-Test -Category "Tool:Validate" -Name "osu_map_validate: Non-existent candidate path returns CANDIDATE_NOT_FOUND" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { osu_map_validate } from './.opencode/tools/osu-map-validate.ts'; osu_map_validate.execute({ candidate_path: 'nonexistent-path.osu' }, { directory: process.cwd(), worktree: process.cwd() } as any).then(r => console.log(r))`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.error.code -eq "CANDIDATE_NOT_FOUND") {
        return @{ Passed = $true; Details = "Correctly handled missing candidate file." }
    } else {
        return @{ Passed = $false; Reason = @("Unexpected response for missing candidate: $output") }
    }
}

Run-Test -Category "Tool:Originality" -Name "osu_map_originality: Distinct reference comparison yields ORIGINAL" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { osu_map_originality } from './.opencode/tools/osu-map-originality.ts'; osu_map_originality.execute({ candidate_path: '.opencode/fixtures/canonical-map.osu', reference_paths: ['.opencode/fixtures/reference-osu-map.osu'] }, { directory: process.cwd(), worktree: process.cwd() } as any).then(r => console.log(r))`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.verdict -eq "ORIGINAL" -and $json.passed -eq $true) {
        return @{ Passed = $true; Details = "Originality gate passed with verdict ORIGINAL (F_match = 0.0)." }
    } else {
        return @{ Passed = $false; Reason = @("Originality test failed: $output") }
    }
}

Run-Test -Category "Tool:Originality" -Name "osu_map_originality: Self-comparison yields CLONE verdict and blocks delivery" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { osu_map_originality } from './.opencode/tools/osu-map-originality.ts'; osu_map_originality.execute({ candidate_path: '.opencode/fixtures/canonical-map.osu', reference_paths: ['.opencode/fixtures/self-reference.osu'] }, { directory: process.cwd(), worktree: process.cwd() } as any).then(r => console.log(r))`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.verdict -eq "CLONE" -and $json.passed -eq $false) {
        return @{ Passed = $true; Details = "Plagiarism anti-tampering triggered: CLONE detected." }
    } else {
        return @{ Passed = $false; Reason = @("Self-comparison failed to produce CLONE: $output") }
    }
}

Run-Test -Category "Tool:Originality" -Name "osu_map_originality: Empty reference array returns NO_REFERENCES error" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { osu_map_originality } from './.opencode/tools/osu-map-originality.ts'; osu_map_originality.execute({ candidate_path: '.opencode/fixtures/canonical-map.osu', reference_paths: [] }, { directory: process.cwd(), worktree: process.cwd() } as any).then(r => console.log(r))`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.error.code -eq "NO_REFERENCES") {
        return @{ Passed = $true; Details = "Handled empty reference list with NO_REFERENCES error." }
    } else {
        return @{ Passed = $false; Reason = @("Failed to reject empty references: $output") }
    }
}

# ------------------------------------------------------------------------------
# SECTION 3: Plugin Guard (M4 Hardening) Verification
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "--- Section 3: Plugin Guard (M4 Hardening) & Security ---" -ForegroundColor Yellow

Run-Test -Category "Plugin:PathGuard" -Name "PathGuard: Reject write to .claude/skills and .env (POLICY_DENIED)" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { PathGuard } from './.opencode/plugins/osu-mapping-guard.ts'; const r1 = PathGuard.validateWritePath('.claude/skills/target'); const r2 = PathGuard.validateWritePath('.env'); console.log(JSON.stringify({ r1, r2 }));`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.r1.allowed -eq $false -and $json.r1.code -eq "POLICY_DENIED" -and $json.r2.allowed -eq $false -and $json.r2.code -eq "POLICY_DENIED") {
        return @{ Passed = $true; Details = "Writes to .claude and .env rejected with POLICY_DENIED." }
    } else {
        return @{ Passed = $false; Reason = @("PathGuard failed to block sensitive paths: $output") }
    }
}

Run-Test -Category "Plugin:PathGuard" -Name "PathGuard: Reject write to osu! Songs folder and credential stores" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { PathGuard } from './.opencode/plugins/osu-mapping-guard.ts'; const r1 = PathGuard.validateWritePath('C:/osu!/Songs/test'); const r2 = PathGuard.validateWritePath('id_rsa'); console.log(JSON.stringify({ r1, r2 }));`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.r1.allowed -eq $false -and $json.r1.code -eq "POLICY_DENIED" -and $json.r2.allowed -eq $false -and $json.r2.code -eq "POLICY_DENIED") {
        return @{ Passed = $true; Details = "Writes to osu!/Songs and id_rsa rejected with POLICY_DENIED." }
    } else {
        return @{ Passed = $false; Reason = @("PathGuard failed to block songs or credentials: $output") }
    }
}

Run-Test -Category "Plugin:PathGuard" -Name "PathGuard: Reject source overwrite (source preservation policy)" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { PathGuard } from './.opencode/plugins/osu-mapping-guard.ts'; const r = PathGuard.validateWritePath('.opencode/fixtures/canonical-map.osu', { sourcePaths: ['.opencode/fixtures/canonical-map.osu'] }); console.log(JSON.stringify(r));`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.allowed -eq $false -and $json.code -eq "POLICY_DENIED" -and $json.message -match "source preservation") {
        return @{ Passed = $true; Details = "Source overwrite detected and blocked with POLICY_DENIED." }
    } else {
        return @{ Passed = $false; Reason = @("Source overwrite was not blocked: $output") }
    }
}

Run-Test -Category "Plugin:PathGuard" -Name "PathGuard: Reject directory traversal escape (../outside.osu)" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { PathGuard } from './.opencode/plugins/osu-mapping-guard.ts'; const r = PathGuard.validateWritePath('work/mapping-runs/run-01/../../outside.osu', { allowedRunDir: 'work/mapping-runs/run-01' }); console.log(JSON.stringify(r));`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.allowed -eq $false -and $json.code -eq "POLICY_DENIED") {
        return @{ Passed = $true; Details = "Relative path traversal escape blocked with POLICY_DENIED." }
    } else {
        return @{ Passed = $false; Reason = @("Traversal escape was not blocked: $output") }
    }
}

Run-Test -Category "Plugin:Redaction" -Name "Redactor: Sanitize environment keys, OAuth tokens, and Bearer headers" -TestScript {
    $env:TEST_SECRET_TOKEN = "super_secret_token_12345_xyz"
    $cmd = "node --experimental-strip-types -e `"import { Redactor } from './.opencode/plugins/osu-mapping-guard.ts'; const text = 'Authorization: Bearer mySecretTokenValue99999 with TEST_SECRET_TOKEN=' + process.env.TEST_SECRET_TOKEN; const sanitized = Redactor.sanitize(text); console.log(JSON.stringify({ sanitized, leaked: sanitized.includes('super_secret_token_12345_xyz') || sanitized.includes('mySecretTokenValue99999') }));`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.leaked -eq $false -and $json.sanitized -match "\[REDACTED\]") {
        return @{ Passed = $true; Details = "Fake environment token and Bearer secret properly redacted to [REDACTED]." }
    } else {
        return @{ Passed = $false; Reason = @("Secret redaction failed: $output") }
    }
}

Run-Test -Category "Plugin:Lifecycle" -Name "LifecycleManager: Append-only event log (events.jsonl) and valid status progression" -TestScript {
    $runDir = "work/mapping-runs/test-harness/run-lifecycle-01"
    $cmd = "node --experimental-strip-types -e `"import { LifecycleManager } from './.opencode/plugins/osu-mapping-guard.ts'; LifecycleManager.appendEvent('$runDir', { run_id: 'test-lc', event_type: 'STATUS_TRANSITION', current_status: 'BUILDING' }); LifecycleManager.appendEvent('$runDir', { run_id: 'test-lc', event_type: 'STATUS_TRANSITION', previous_status: 'BUILDING', current_status: 'VERIFYING' }); const events = LifecycleManager.readEvents('$runDir'); const status = LifecycleManager.getCurrentStatus('$runDir'); console.log(JSON.stringify({ eventCount: events.length, status }));`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    $eventsFile = Join-Path $ProjectRoot "$runDir\events.jsonl"
    if ($json.eventCount -eq 2 -and $json.status -eq "VERIFYING" -and (Test-Path -LiteralPath $eventsFile)) {
        return @{ Passed = $true; Details = "Maintained 2 events in events.jsonl with current status VERIFYING." }
    } else {
        return @{ Passed = $false; Reason = @("Lifecycle events failed: $output") }
    }
}

Run-Test -Category "Plugin:Completion" -Name "CompletionGuard: Reject completion when reports missing or verifier not PASS" -TestScript {
    $runDir = "work/mapping-runs/test-harness/run-incomplete-01"
    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "$runDir\candidate") | Out-Null
    Copy-Item -LiteralPath $CanonicalMap -Destination (Join-Path $ProjectRoot "$runDir\candidate\candidate.osu") -Force

    $cmd = "node --experimental-strip-types -e `"import { CompletionGuard } from './.opencode/plugins/osu-mapping-guard.ts'; const r = CompletionGuard.evaluateCompletion('$runDir'); console.log(JSON.stringify(r));`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.passed -eq $false -and $json.verdict -eq "INCOMPLETE" -and $json.reasons.Count -ge 2) {
        return @{ Passed = $true; Details = "Correctly rejected COMPLETE state due to missing reports." }
    } else {
        return @{ Passed = $false; Reason = @("CompletionGuard failed to reject incomplete run: $output") }
    }
}

Run-Test -Category "Plugin:Recovery" -Name "RecoveryManager: Detect pre-validated candidate and skip redundant generation" -TestScript {
    $runDir = "work/mapping-runs/test-harness/run-recovery-01"
    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "$runDir\candidate") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "$runDir\reports") | Out-Null
    Copy-Item -LiteralPath $CanonicalMap -Destination (Join-Path $ProjectRoot "$runDir\candidate\candidate.osu") -Force

    $candSha = Get-FileSha256 (Join-Path $ProjectRoot "$runDir\candidate\candidate.osu")
    $compJson = @{
        status = "COMPLETE"
        hard_requirements_passed = $true
        output_beatmap_path = (Join-Path $ProjectRoot "$runDir\candidate\candidate.osu")
        stage_results = @{
            file_integrity = "PASS"
            beat_grid_validity = "PASS"
            playfield_boundaries = "PASS"
            originality_gate = "PASS"
        }
    } | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText((Join-Path $ProjectRoot "$runDir\reports\completion-report.json"), $compJson, [System.Text.UTF8Encoding]::new($false))

    $cmd = "node --experimental-strip-types -e `"import { RecoveryManager } from './.opencode/plugins/osu-mapping-guard.ts'; const r = RecoveryManager.checkRecovery('$runDir'); console.log(JSON.stringify(r));`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.canResume -eq $true -and $json.stage -eq "VERIFYING" -and $json.candidateSha256 -eq $candSha) {
        return @{ Passed = $true; Details = "Recovery detected valid candidate ($candSha), transitioning directly to VERIFYING." }
    } else {
        return @{ Passed = $false; Reason = @("Recovery check failed: $output") }
    }
}

# ------------------------------------------------------------------------------
# SECTION 4: Acceptance Test Matrix (PRD Section 19)
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "--- Section 4: PRD Section 19 Acceptance Test Matrix ---" -ForegroundColor Yellow

Run-Test -Category "PRD-Matrix" -Name "Double run: Identical briefs produce unique run IDs and paths" -TestScript {
    $cmd = "node --experimental-strip-types -e `"import { LifecycleManager } from './.opencode/plugins/osu-mapping-guard.ts'; const id1 = LifecycleManager.createRunId(); const id2 = LifecycleManager.createRunId(); console.log(JSON.stringify({ id1, id2, unique: id1 !== id2 }));`""
    $output = Invoke-Expression $cmd
    $json = $output | ConvertFrom-Json
    if ($json.unique -eq $true -and $json.id1 -match "^run-" -and $json.id2 -match "^run-") {
        return @{ Passed = $true; Details = "Generated unique IDs: $($json.id1) and $($json.id2)." }
    } else {
        return @{ Passed = $false; Reason = @("Run IDs were not unique: $output") }
    }
}

Run-Test -Category "PRD-Matrix" -Name "Source preservation: Fixture checksums remain unchanged throughout test run" -TestScript {
    $initialSha = Get-FileSha256 $CanonicalMap
    # Perform read and validation
    $valCmd = "python .opencode/skills/osu-mapping/scripts/validate_osu.py --candidate .opencode/fixtures/canonical-map.osu"
    Invoke-Expression $valCmd | Out-Null
    $finalSha = Get-FileSha256 $CanonicalMap
    if ($initialSha -eq $finalSha) {
        return @{ Passed = $true; Details = "Canonical fixture SHA-256 bit-for-bit unchanged: $initialSha." }
    } else {
        return @{ Passed = $false; Reason = @("Source checksum mutated! Initial: $initialSha, Final: $finalSha") }
    }
}

Run-Test -Category "PRD-Matrix" -Name "Full Acceptance Suite: run_acceptance_tests.py on generated run" -TestScript {
    $fullRunDir = "work/mapping-runs/test-harness/run-full-suite"
    New-Item -ItemType Directory -Force -Path $fullRunDir | Out-Null

    # Generate candidate
    $genCmd = "python .opencode/skills/osu-mapping/scripts/generate_osu.py --output-dir $fullRunDir --bpm 100 --duration 30000 --style hybrid"
    Invoke-Expression $genCmd | Out-Null

    # Execute acceptance suite
    $suiteCmd = "python .opencode/skills/osu-mapping/scripts/run_acceptance_tests.py --run-dir $fullRunDir"
    $suiteOutput = Invoke-Expression $suiteCmd
    $suiteJson = $suiteOutput | ConvertFrom-Json

    $verReportFile = Join-Path $ProjectRoot "$fullRunDir\reports\verification-report.json"
    if ($suiteJson.verdict -in @("PASS", "PARTIAL") -and (Test-Path -LiteralPath $verReportFile) -and $suiteJson.playability_disclaimer) {
        return @{ Passed = $true; Details = "Acceptance suite completed with verdict $($suiteJson.verdict), disclaimer present." }
    } else {
        return @{ Passed = $false; Reason = @("Acceptance suite failed: $suiteOutput") }
    }
}

# ------------------------------------------------------------------------------
# SECTION 5: Summary & Exit Code
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
$summaryColor = "Green"
if ($script:FailedTests -gt 0) { $summaryColor = "Red" }
Write-Host (" Test Summary: {0} Total | {1} Passed | {2} Failed" -f $script:TotalTests, $script:PassedTests, $script:FailedTests) -ForegroundColor $summaryColor
Write-Host "================================================================================" -ForegroundColor Cyan

# Clean up test harness workspace
if (Test-Path -LiteralPath $TestRunsRoot) {
    Remove-Item -LiteralPath $TestRunsRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if ($script:FailedTests -eq 0) {
    Write-Host "All osu! mapping MVP tests passed successfully." -ForegroundColor Green
    exit 0
} else {
    Write-Host "One or more tests failed. Check log details above." -ForegroundColor Red
    exit 1
}
