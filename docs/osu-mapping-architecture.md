# osu! Mapping Architecture & System Design

## 1. System Overview & Three-Layer Design

The osu! mapping subsystem within MultiAI Classroom is structured into three discrete layers:

```
+-----------------------------------------------------------------------------+
|                               3-LAYER DESIGN                                |
+-----------------------------------------------------------------------------+

  [ Layer 1: Skill Layer ]  (.opencode/skills/osu-mapping/)
  * Workflow rules & operating procedures (SKILL.md)
  * Format reference (references/osu_file_format.md)
  * Style taxonomy & pattern catalog (references/style_taxonomy.md)
  * Anti-plagiarism & similarity rules (references/originality-policy.md)
  * Python mapping & validation engine (scripts/*.py)

                                   |
                                   v

  [ Layer 2: Custom Tools Layer ]  (.opencode/tools/)
  * Typed OpenCode tool declarations using @opencode-ai/plugin
  * osu_map_inspect.ts       -> Metadata & structure inspector
  * osu_map_generate.ts      -> Two-pass rhythm/geometry generator
  * osu_map_validate.ts      -> Static & dynamic validator
  * osu_map_originality.ts   -> Plagiarism & n-gram similarity checker
  * Input sanitization, path normalization & JSON serialization

                                   |
                                   v

  [ Layer 3: Plugin Guard Layer ]  (.opencode/plugins/osu-mapping-guard.ts)
  * Run lifecycle orchestration (PLANNED -> BUILDING -> VERIFYING -> COMPLETE)
  * Path Guard: Rejection of path escapes, sensitive targets, and overwrites
  * Secret Redaction: Auto-sanitization of tokens, auth headers, and env keys
  * Completion Guard: Artifact existence, checksum matching & report gates
  * Recovery Manager: Resumes interrupted runs without re-generation
```

### Layer Rationale
- **Skill Layer**: Provides domain-specific heuristics and mathematical algorithms for timing, pattern generation, cursor simulation, and originality checks.
- **Custom Tools Layer**: Provides strongly typed, schema-validated execution wrappers around Python scripts, preventing models from executing arbitrary shell strings or passing malformed arguments.
- **Plugin Guard Layer**: Enforces security policies, immutability constraints, and verification integrity before declaring runs complete.

---

## 2. End-to-End Data Flow

```text
               +-------------------------------------------+
               | User Prompt / input/mapping-brief.json    |
               +-------------------------------------------+
                                     |
                                     v
                 +---------------------------------------+
                 |                TEACHER                |
                 | - Normalizes objective & parameters   |
                 | - Assigns unique run-id & run dir     |
                 +---------------------------------------+
                                     |
                                     v
          +-----------------------------------------------------+
          |                  STUDENT ARCHITECT                  |
          | - Calls: osu_map_inspect                            |
          | - Validates audio & timing integrity                |
          | - Determines style profile & difficulty band        |
          | - Produces: plan/mapping-plan.json                  |
          +-----------------------------------------------------+
                                     |
                                     v
          +-----------------------------------------------------+
          |                   STUDENT BUILDER                   |
          | - Reads: mapping-plan.json                          |
          | - Calls: osu_map_generate                           |
          |     Pass 1: Timing engine & rhythm anchors          |
          |     Pass 2: Geometry, jumps, flow & sliders         |
          | - Produces: candidate/candidate.osu                 |
          |             reports/provenance.json                 |
          |             reports/completion-report.json          |
          +-----------------------------------------------------+
                                     |
                                     v
          +-----------------------------------------------------+
          |                  STUDENT VERIFIER                   |
          | - Calls: osu_map_validate                           |
          | - Calls: osu_map_originality                        |
          | - Executes: run_acceptance_tests.py                 |
          | - Verifies bit-for-bit source file immutability     |
          | - Evaluates all Acceptance Criteria (AC-01 - AC-14) |
          | - Produces: reports/verification-report.json        |
          +-----------------------------------------------------+
                                     |
                                     v
          +-----------------------------------------------------+
          |                 STUDENT DOCUMENTER                  |
          | - Synthesizes verified evidence from reports        |
          | - Attaches mandatory human playability boundary     |
          | - Produces: handoff documentation & test summaries  |
          +-----------------------------------------------------+
                                     |
                                     v
                 +---------------------------------------+
                 |                TEACHER                |
                 | - Evaluates CompletionGuard gates     |
                 | - Delivers final verdict:             |
                 |   COMPLETE | INCOMPLETE | FAILED      |
                 +---------------------------------------+
```

---

## 3. Component Responsibilities

| Agent Role | Access Permissions | Primary Responsibility | Prohibited Actions |
|---|---|---|---|
| **Teacher** | Read-Only | Orchestration, parameter validation, handoff forwarding, final verdict synthesis | Editing beatmap files, modifying reports, declaring completion without verified evidence |
| **Student Architect** | Read-Only | Inspects source and reference files via `osu_map_inspect`, resolves timing, outputs `mapping-plan.json` | Executing generator, creating candidates, modifying source files |
| **Student Builder** | Read/Write (run dir only) | Executes two-pass beatmap generation via `osu_map_generate`, creates candidate `.osu`, `provenance.json`, and `completion-report.json` | Writing outside `work/mapping-runs/<run-id>/`, modifying source files, declaring human playability |
| **Student Verifier** | Read/Write (reports dir only) | Independently runs test suites, checks checksums, evaluates ACs, outputs `verification-report.json` | Editing candidate files, modifying plan contracts, trusting Builder self-claims |
| **Student Documenter** | Read/Write (docs only) | Synthesizes verified findings into handoff docs with explicit playability disclaimers | Fabricating unverified passes, altering verdicts, modifying source code |

---

## 4. Artifact Contracts & Data Specifications

All stage handoffs are governed by strict JSON schemas located in `schemas/`:

```text
schemas/
├── mapping-brief.schema.json
├── mapping-plan.schema.json
├── completion-report.schema.json
└── verification-report.schema.json
```

### 4.1 Schema Contract Summary

| Artifact File | Schema ID | Producer | Key Required Fields |
|---|---|---|---|
| `mapping-brief.json` | `mapping-brief.schema.json` | User / Teacher | `mode`, `ruleset`, `bpm`, `offset_ms`, `style`, `target_star`, `output_root`, `constraints` |
| `mapping-plan.json` | `mapping-plan.schema.json` | Student Architect | `run_id`, `mode`, `timing_source`, `style_profile`, `expected_artifacts`, `acceptance_criteria` |
| `provenance.json` | `provenance.schema.json` | Student Builder | `run_id`, `timestamp_start`, `scripts_manifest`, `inputs_manifest`, `candidate_manifest`, `tool_invocations` |
| `completion-report.json` | `completion-report.schema.json` | Student Builder | `status`, `output_beatmap_path`, `stage_results`, `hard_requirements_passed`, `warnings`, `errors` |
| `verification-report.json` | `verification-report.schema.json` | Student Verifier | `verdict`, `commands_executed`, `acceptance_criteria_results`, `source_checksum_unchanged`, `playability_disclaimer` |

---

## 5. Error Model & Recovery Architecture

### 5.1 Standardized Error Categories

Every tool and script returns errors in a consistent JSON format:

```json
{
  "error": {
    "code": "POLICY_DENIED",
    "category": "security",
    "message": "Write access to sensitive target '.env' is blocked by security policy.",
    "recoverable": false
  }
}
```

Standard error codes include:
- `INVALID_INPUT`: Malformed parameters, out-of-range star rating, or missing required fields.
- `ACCESS_DENIED` / `POLICY_DENIED`: Unauthorized file read/write attempt (sensitive directories, path traversal).
- `FILE_NOT_FOUND` / `CANDIDATE_NOT_FOUND`: Target file or candidate does not exist.
- `SCRIPT_NOT_FOUND`: Internal generator or validator script missing.
- `NO_REFERENCES`: Originality check invoked with empty reference list when resolution is required.
- `SPAWN_ERROR`: Subprocess spawning failure.
- `ORIGINALITY_BLOCKED`: Candidate classified as `CLONE` or `NEAR_CLONE`.
- `VALIDATION_FAILED`: Beat-grid off-grid objects, bounds violation, or coverage deficiency.

### 5.2 Interruption Recovery Flow (`RecoveryManager`)

If an execution run is interrupted (e.g. timeout, process restart), `RecoveryManager` supports resuming without re-executing completed stages:

```
                +------------------------------------+
                | RecoveryManager.checkRecovery()    |
                +------------------------------------+
                                  |
            +---------------------+---------------------+
            |                                           |
            v                                           v
[ Candidate Missing / Incomplete ]           [ Candidate & Completion OK ]
            |                                           |
            v                                           v
    canResume: false                             canResume: true
    stage: "NONE"                                Check verification report
    Action: Restart from PLANNED                        |
                                           +------------+------------+
                                           |                         |
                                           v                         v
                              [ Verifier report PASS ]     [ Verifier Pending ]
                                           |                         |
                                           v                         v
                                    stage: "COMPLETE"        stage: "VERIFYING"
                                    Skip to synthesis        Resume Verifier
```

---

## 6. Security Architecture

### 6.1 Path Guard & Sandbox Containment
- **Canonical Path Resolution**: Uses `fs.realpathSync` to resolve symbolic links and directory junctions, preventing jailbreaks via symlink escapes.
- **Run Directory Containment**: All writes are restricted to `work/mapping-runs/<run-id>/`.
- **Forbidden Targets**: Writes or reads targeting `.env`, `.claude`, `.git`, `node_modules`, `id_rsa`, `.ssh`, `credentials.json`, and `osu!\Songs\` are unconditionally blocked with `POLICY_DENIED`.

### 6.2 Source File Immutability
- Input audio and source beatmaps are treated as strictly read-only.
- The system calculates the SHA-256 hash of all input assets before execution and asserts identical hash values upon run completion.

### 6.3 Sensitive Data Redaction
- The `Redactor` class sanitizes logs, tool inputs, and tool outputs.
- Regex rules detect and mask API keys, OAuth tokens, Bearer authentication headers, and active environment variables.
- Large raw `.osu` beatmap dumps are summarized in logs rather than echoed in full.
