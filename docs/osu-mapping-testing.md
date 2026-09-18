# osu! Mapping Test Strategy & Verification Harness

## 1. Overview & Verification Scope

The test suite for `osu-mapping` ensures mathematical precision, format compliance, anti-plagiarism integrity, and security sandboxing across all components.

Verification covers four primary tiers:
1. **Fixtures & Environment Integrity**: Verification of baseline beatmaps and test assets.
2. **Typed Custom Tools Execution**: Direct invocation of `osu_map_inspect`, `osu_map_generate`, `osu_map_validate`, and `osu_map_originality`.
3. **Plugin Guard & Security Hardening**: Verification of `PathGuard`, `Redactor`, `LifecycleManager`, `CompletionGuard`, and `RecoveryManager`.
4. **PRD Section 19 Acceptance Matrix**: End-to-end evaluation of acceptance criteria AC-01 through AC-14.

---

## 2. PRD Section 19 Test Matrix

| Test ID | Test Scenario | Target / Fixture | Verification Method | Expected Outcome | Status |
|---|---|---|---|---|---|
| **AC-01** | Skill Discovery | `.opencode/skills/osu-mapping/SKILL.md` | Frontmatter inspection & agent loader | Skill discovered and accessible to Teacher/Builder | PASS |
| **AC-02** | Baseline Skill Preservation | `C:\Users\PC SERANG 01\.claude\skills\osu-beatmap` | SHA-256 pre/post check | Bit-for-bit unchanged; zero mutations | PASS |
| **AC-03** | Custom Tool Schema Rejection | Missing audio/BPM or invalid path | Direct tool execution | Structured JSON error (`INVALID_INPUT` / `ACCESS_DENIED`) | PASS |
| **AC-04** | Unique Outputs / Idempotency | Consecutive runs with identical brief | `LifecycleManager.createRunId()` | Unique run IDs and distinct directory paths | PASS |
| **AC-05** | Source Immutability | `canonical-map.osu` | Modify run with SHA-256 comparison | Source file checksum remains identical | PASS |
| **AC-06** | Validator Parity | `canonical-map.osu` | `osu_map_validate` vs Python CLI | Status, exit code (0), and stage verdicts match | PASS |
| **AC-07** | Originality & Anti-Clone Gate | `self-reference.osu` vs `canonical-map.osu` | `osu_map_originality` | Verdict `CLONE` ($F_{\text{match}} = 1.0$), delivery blocked | PASS |
| **AC-08** | Full Song Coverage Gate | `short-coverage-map.osu` | `validate_osu.py --audio` | Fails coverage check (< 95%), run `INCOMPLETE` | PASS |
| **AC-09** | Beat-Grid Snapping & Off-Grid Rejection | `off-grid-map.osu` | `validate_osu.py` | Beat-grid stage fails (5 off-grid objects detected) | PASS |
| **AC-10** | Path Guard / Traversal Escape | `../outside.osu`, `.env`, `.claude` | `PathGuard.validateWritePath()` | Returns `POLICY_DENIED`, write blocked | PASS |
| **AC-11** | Secret & Token Redaction | Fake OAuth / Bearer token in env | `Redactor.sanitize()` | Redacted to `[REDACTED]`, 0 secrets leaked | PASS |
| **AC-12** | Full Classroom Orchestration Flow | Sequential 4-student chain | Agent task handoffs & report logs | Teacher passes concrete handoffs in dependency order | PASS |
| **AC-13** | Interruption / Failure Handling | Incomplete report fixture | `CompletionGuard.evaluateCompletion()` | Verdict `INCOMPLETE`/`FAILED`, no false completion | PASS |
| **AC-14** | Human Playability Boundary | `verification-report.json` | Report inspection & handoff check | Mandatory playability disclaimer attached | PASS |
| **AC-15** | One Real Song Dry Run | Live audio track & references | End-to-end mapping pipeline | *Pending full live trial on real music track* | PENDING |

---

## 3. Fixture Descriptions

All test fixtures reside in `.opencode/fixtures/`:

```text
.opencode/fixtures/
├── canonical-map.osu              # Valid v14 beatmap (25 hit objects, snapped, valid bounds)
├── off-grid-map.osu               # Beatmap containing 5 off-grid objects for negative snapping tests
├── short-coverage-map.osu         # Beatmap with truncated duration (<95% coverage)
├── self-reference.osu             # Exact clone fixture used for anti-plagiarism gate testing
├── reference-osu-map.osu          # Distinct reference beatmap for originality testing
└── sample-audio-placeholder.txt   # Mock audio stream descriptor for coverage testing
```

---

## 4. How to Run the Tests

### 4.1 Master Test Suite (PowerShell)

The primary verification harness runs all fixture, tool, plugin, and matrix tests:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test-osu-mapping.ps1
```

Or from PowerShell Core (`pwsh`):

```powershell
pwsh scripts/test-osu-mapping.ps1
```

### 4.2 Running Python Acceptance Suite Directly

To run the Python acceptance test runner on any generated run directory:

```powershell
python .opencode/skills/osu-mapping/scripts/run_acceptance_tests.py --run-dir work/mapping-runs/<run-id>
```

### 4.3 Testing Individual Custom Tools (Node.js)

Inspect a beatmap:
```powershell
node --experimental-strip-types -e "import { osu_map_inspect } from './.opencode/tools/osu-map-inspect.ts'; osu_map_inspect.execute({ path: '.opencode/fixtures/canonical-map.osu' }, { directory: process.cwd(), worktree: process.cwd() } as any).then(console.log)"
```

Validate a candidate:
```powershell
node --experimental-strip-types -e "import { osu_map_validate } from './.opencode/tools/osu-map-validate.ts'; osu_map_validate.execute({ candidate_path: '.opencode/fixtures/canonical-map.osu' }, { directory: process.cwd(), worktree: process.cwd() } as any).then(console.log)"
```

Check originality:
```powershell
node --experimental-strip-types -e "import { osu_map_originality } from './.opencode/tools/osu-map-originality.ts'; osu_map_originality.execute({ candidate_path: '.opencode/fixtures/canonical-map.osu', reference_paths: ['.opencode/fixtures/reference-osu-map.osu'] }, { directory: process.cwd(), worktree: process.cwd() } as any).then(console.log)"
```

---

## 5. Expected Test Outcomes

When executing `scripts/test-osu-mapping.ps1`, the output should reflect:
- **Total Tests**: 16
- **Passed Tests**: 16
- **Failed Tests**: 0
- **Exit Code**: `0`

Example console log:
```text
================================================================================
 osu! Mapping MVP - Comprehensive Test Suite & Plugin Guard Verification
 Target Directory: C:\Users\PC SERANG 01\.omniroute\multiai-classroom
================================================================================

--- Section 1: Fixtures & Environment Integrity ---
  [PASS] Test 01 [Fixtures]     : Test fixtures existence and non-empty sizes
  [PASS] Test 02 [Fixtures]     : Canonical map format and hit object count

--- Section 2: Custom Tools Typed Execution ---
  [PASS] Test 03 [Tool:Inspect] : osu_map_inspect: Parse canonical .osu file
  [PASS] Test 04 [Tool:Inspect] : osu_map_inspect: Reject sensitive path (.env / credentials)
  [PASS] Test 05 [Tool:Generate]: osu_map_generate: Generate candidate in designated run directory
  [PASS] Test 06 [Tool:Generate]: osu_map_generate: Reject invalid target path containing .env
  [PASS] Test 07 [Tool:Validate]: osu_map_validate: Canonical map validation verdict PASS
  [PASS] Test 08 [Tool:Validate]: osu_map_validate: Off-grid map detection (beat_grid_validity FAIL)
  [PASS] Test 09 [Tool:Validate]: osu_map_validate: Non-existent candidate path returns CANDIDATE_NOT_FOUND
  [PASS] Test 10 [Tool:Originality]: osu_map_originality: Distinct reference comparison yields ORIGINAL
  [PASS] Test 11 [Tool:Originality]: osu_map_originality: Self-comparison yields CLONE verdict and blocks delivery
  [PASS] Test 12 [Tool:Originality]: osu_map_originality: Empty reference array returns NO_REFERENCES error

--- Section 3: Plugin Guard (M4 Hardening) & Security ---
  [PASS] Test 13 [Plugin:PathGuard]: PathGuard: Reject write to .claude/skills and .env (POLICY_DENIED)
  [PASS] Test 14 [Plugin:PathGuard]: PathGuard: Reject write to osu! Songs folder and credential stores
  [PASS] Test 15 [Plugin:PathGuard]: PathGuard: Reject source overwrite (source preservation policy)
  [PASS] Test 16 [Plugin:PathGuard]: PathGuard: Reject directory traversal escape (../outside.osu)
  [PASS] Test 17 [Plugin:Redaction]: Redactor: Sanitize environment keys, OAuth tokens, and Bearer headers
  [PASS] Test 18 [Plugin:Lifecycle]: LifecycleManager: Append-only event log and valid status progression
  [PASS] Test 19 [Plugin:Completion]: CompletionGuard: Reject completion when reports missing or verifier not PASS
  [PASS] Test 20 [Plugin:Recovery]: RecoveryManager: Detect pre-validated candidate and skip redundant generation

--- Section 4: PRD Section 19 Acceptance Test Matrix ---
  [PASS] Test 21 [PRD-Matrix]   : Double run: Identical briefs produce unique run IDs and paths
  [PASS] Test 22 [PRD-Matrix]   : Source preservation: Fixture checksums remain unchanged throughout test run
  [PASS] Test 23 [PRD-Matrix]   : Full Acceptance Suite: run_acceptance_tests.py on generated run

================================================================================
 Test Summary: 23 Total | 23 Passed | 0 Failed
================================================================================
All osu! mapping MVP tests passed successfully.
```

---

## 6. Known Test Limitations

1. **Synthetic Audio & Timings**:
   - Current automated suites test mathematical integrity using static fixtures (`canonical-map.osu`, `off-grid-map.osu`).
   - AC-15 requires a full real-world audio track trial with community mapper reference sets.
2. **Gameplay Ergonomics**:
   - Automated testing validates geometric bounds, distance snapping, velocity, and jump angle distribution.
   - Physical strain, reading clarity, and hand flow require manual human playtesting.

---

## 7. Regression Testing Guidelines

When modifying generator logic, timing calculations, or validation algorithms:

1. **Check Fixture Checksums**: Verify that fixtures in `.opencode/fixtures/` have not been altered.
2. **Run Harness**: Execute `scripts/test-osu-mapping.ps1` to confirm all 23 checks pass.
3. **Verify Global Skill Untouched**: Confirm that files in `C:\Users\PC SERANG 01\.claude\skills\osu-beatmap` remain unmodified.
4. **Validate Artifact Contracts**: Run schema validation on generated reports against `schemas/*.schema.json`.
