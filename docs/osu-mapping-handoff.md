# osu! Mapping MVP - User Handoff Guide

## 1. Product Overview

The `osu-mapping` capability is a project-local skill and toolset for OpenCode that plans, generates, modifies, and verifies osu!standard (`.osu` v14 format) beatmaps through an automated MultiAI Classroom workflow.

Mapping operations are coordinated across specialized agents:
- **Teacher**: Orchestrates mapping briefs, delegates tasks, and synthesizes final verdicts strictly from verified evidence.
- **Student Architect**: Inspects inputs, locks down timing, determines style profiles, and creates `mapping-plan.json`.
- **Student Builder**: Executes generation in two distinct passes (Rhythm Pass then Geometry Pass) using typed tools (`osu_map_*`) and writes candidate files strictly to isolated run directories.
- **Student Verifier**: Independently evaluates candidate beatmaps against acceptance criteria and produces `verification-report.json`.
- **Student Documenter**: Synthesizes verified facts into human-readable handoff documentation with explicit playability boundaries.

---

## 2. Prerequisites & Requirements

Before running the mapping workflow, ensure the following prerequisites are installed and running:

### System Prerequisites
- **Python**: 3.10 or higher (Python 3.11+ recommended) accessible in system `PATH`
- **OpenCode**: Version 1.18.x (tested on 1.18.30)
- **Node.js**: Version 18 or higher (supports `--experimental-strip-types` for running TypeScript tools)
- **OmniRoute**: Local loopback instance running at `http://127.0.0.1:8000/v1`
- **PowerShell**: Windows PowerShell 5.1 or PowerShell Core 7+ (`pwsh`)

### Pre-flight Checklist
- [ ] Confirm Python is available: `python --version`
- [ ] Confirm Node.js is available: `node --version`
- [ ] Confirm OmniRoute loopback is active on port 8000
- [ ] Ensure working directory is set to project root: `C:\Users\PC SERANG 01\.omniroute\multiai-classroom`

---

## 3. Quick Start

### Starting MultiAI Classroom
Launch the classroom environment from PowerShell:

```powershell
cd 'C:\Users\PC SERANG 01\.omniroute\multiai-classroom'
.\Start-Classroom.ps1
```

### Triggering a Mapping Run
Once the classroom shell is active, provide a prompt to Teacher:

```text
Read examples/osu-mapping-skill-plugin-prd.md and execute beatmap generation for the project-local workflow. Use the full classroom flow.
```

Or execute directly with a brief:

```powershell
.\Start-Classroom.ps1 -Prompt "Read work/mapping-brief.json and execute beatmap generation using the full classroom flow."
```

---

## 4. Input Requirements (`mapping-brief.json`)

All mapping tasks start from a structured input brief validated against `schemas/mapping-brief.schema.json`.

### Brief Schema Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `mode` | `string` | Yes | Execution mode: `"generate"`, `"modify"`, `"validate"`, or `"resume"` |
| `ruleset` | `string` | Yes | Target game mode. Must be `"osu"` (standard Mode 0) |
| `audio_path` | `string` / `null` | Optional | Absolute or workspace path to song audio file (`.mp3`, `.ogg`, `.wav`) |
| `source_beatmap_path` | `string` / `null` | Optional | Path to existing `.osu` file (required for `modify` mode) |
| `bpm` | `number` | Yes | Song tempo in BPM (`bpm > 0`) |
| `offset_ms` | `integer` | Yes | Offset of the first downbeat in milliseconds |
| `style` | `string` | Yes | Target style profile: `"aimslop"`, `"flow_aim"`, or `"hybrid"` |
| `target_star` | `object` | Yes | Difficulty band `{ "min": number, "max": number }` ($0.5 \le \text{min} \le \text{max} \le 10.0$) |
| `references` | `array` | Optional | List of local reference `.osu` beatmap paths |
| `mapper_reference` | `object` / `null` | Optional | Mapper reference profile (e.g. preferred CS, AR) |
| `output_root` | `string` | Yes | Root directory for run outputs (`"work/mapping-runs"`) |
| `constraints` | `object` | Yes | Safety and gate flags (`preserve_source`, `overwrite`, `require_full_song_coverage`, `require_originality_resolution`) |

### Example `mapping-brief.json`

```json
{
  "mode": "generate",
  "ruleset": "osu",
  "audio_path": "work/audio/song.mp3",
  "source_beatmap_path": null,
  "bpm": 180.0,
  "offset_ms": 1250,
  "style": "hybrid",
  "target_star": {
    "min": 5.0,
    "max": 5.8
  },
  "references": [
    ".opencode/fixtures/canonical-map.osu"
  ],
  "mapper_reference": null,
  "output_root": "work/mapping-runs",
  "constraints": {
    "preserve_source": true,
    "overwrite": false,
    "require_full_song_coverage": true,
    "require_originality_resolution": true
  }
}
```

---

## 5. Output Artifacts

Every run generates an isolated directory under `work/mapping-runs/<run-id>/`:

```text
work/mapping-runs/<run-id>/
├── input/
│   └── mapping-brief.json       # Normalized brief contract
├── plan/
│   └── mapping-plan.json        # Architect planning contract & criteria
├── candidate/
│   └── candidate.osu            # Generated/modified osu! beatmap
├── reports/
│   ├── provenance.json          # Tool execution log & SHA-256 hashes
│   ├── completion-report.json   # Builder stage summary & self-checks
│   └── verification-report.json # Verifier independent evaluation
├── logs/
│   └── run.log                  # Redacted execution log
└── events.jsonl                 # Append-only lifecycle event journal
```

### How to Preview & Import Generated Beatmaps
1. Locate `candidate.osu` at `work/mapping-runs/<run-id>/candidate/candidate.osu`.
2. To test in **osu! (stable)**:
   - Create a subfolder in `osu!\Songs\TestMap <run-id>\`.
   - Copy `candidate.osu` and your audio file into that folder.
   - Ensure the `AudioFilename` property in `[General]` matches the copied audio filename.
   - Press `F5` on the osu! song select screen to refresh beatmaps.
3. To test in **osu! (lazer)**:
   - Create an `.osz` archive (zip archive containing `candidate.osu` and audio file, renamed to `.osz`).
   - Drag and drop the `.osz` file into the osu!(lazer) window.

---

## 6. Running the Test Suite

A standalone test harness validates all custom tools, acceptance criteria (PRD Section 19), path guards, anti-plagiarism gates, and redaction policies.

### Execute Test Harness

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test-osu-mapping.ps1
```

Or from PowerShell 7:

```powershell
pwsh scripts/test-osu-mapping.ps1
```

### Test Coverage Breakdown
- **Fixtures & Environment**: Validates existence and syntax of all 6 test fixtures.
- **Custom Tools Execution**: Tests typed wrappers (`osu_map_inspect`, `osu_map_generate`, `osu_map_validate`, `osu_map_originality`).
- **Plugin Guard & Security**: Tests `PathGuard` against directory traversal and sensitive path writes (`.env`, `.claude/skills`, `osu!/Songs`), `Redactor` for secret sanitization, and `LifecycleManager` event logging.
- **Acceptance Criteria Matrix**: Verifies unique run ID generation, bit-for-bit source file immutability, and full acceptance test execution.

---

## 7. Safety Boundaries

The system enforces strict operating limits to protect user environments and source materials:

- **Source File Immutability**: Source beatmaps and audio files are strictly read-only. Modifying an existing map writes a new `.osu` file into `work/mapping-runs/<run-id>/candidate/` and verifies that the source file SHA-256 remains unchanged.
- **No Global Skill Tampering**: Global Claude skills (`C:\Users\PC SERANG 01\.claude\skills\osu-beatmap`) are never modified.
- **Directory Traversal Protection**: All file writes outside `work/mapping-runs/<run-id>/` are rejected with `POLICY_DENIED`.
- **No Direct Songs Folder Writes**: The system will not write directly to `C:\osu!\Songs\` during automated runs.
- **Secret & Credential Redaction**: `.env` files, API tokens, OAuth keys, SSH keys, and `Authorization: Bearer` headers are blocked from inspection and redacted from logs, reports, and handoffs.

---

## 8. Known Limitations

1. **Human Playability Not Verified**:
   > *Automated static, geometry, and originality validation passed. Human gameplay feel, ergonomic strain, reading clarity, and modding readiness require manual playtesting in osu!.*
2. **AC-15 (Real Dry Run) Pending**:
   - Acceptance criteria AC-01 through AC-14 have passed in automated verification.
   - AC-15 (full end-to-end dry run on a live real-world audio track with community reference sets) has not yet been performed.
3. **M4 Hardening Plugin is Preview**:
   - The plugin guard module (`.opencode/plugins/osu-mapping-guard.ts`) provides full unit-tested guard classes (`PathGuard`, `LifecycleManager`, `CompletionGuard`, `Redactor`, `RecoveryManager`), but OpenCode plugin hook runtime integration is in preview status.
4. **Game Mode Restriction**:
   - Only standard osu! (Mode 0) is supported. Taiko, Catch, and Mania are rejected.

---

## 9. Verdict & Status

- **Status**: **Project-Local Beta**
- **Readiness**: Milestones M0 through M3 complete; M4 preview included. Suitable for local testing and supervised beatmap generation. Not intended for unsupervised production deployment.
