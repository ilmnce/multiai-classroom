---
name: osu-mapping
description: "Create, modify, and validate osu!standard beatmaps through a MultiAI Classroom workflow. Plans rhythm/geometry generation, runs typed validation, and enforces originality gates."
---

# osu! Mapping Skill (`osu-mapping`)

## 1. Purpose & Overview

The `osu-mapping` skill defines standard operating procedures, data contracts, safety constraints, and validation gates for creating, modifying, and verifying osu!standard (`osu`) beatmap files within the **MultiAI Classroom** system.

Mapping is executed across specialized agent roles:
- **Teacher**: Orchestrates mapping brief, validates pre-requisites, dispatches stages, and delivers final verdict based solely on verified evidence.
- **Student Architect**: Inspects inputs, locks down timing, determines style profiles, and produces `mapping-plan.json`.
- **Student Builder**: Executes generation in two distinct passes (Rhythm Pass then Geometry Pass) via typed tools (`osu_map_*`) and writes candidate files strictly to isolated run directories.
- **Student Verifier**: Independently runs acceptance suites and static/dynamic validators to produce `verification-report.json`.
- **Student Documenter**: Synthesizes verified facts into human-readable handoff documentation with clear playability disclaimers.

---

## 2. Workflow Selection

The skill operates under four explicit workflow modes:

```
                  +--------------------------------+
                  | Input: mapping-brief.json      |
                  +--------------------------------+
                                  |
                                  v
                    [ Workflow Mode Selection ]
                                  |
         +----------------+-------+-------+----------------+
         |                |               |                |
         v                v               v                v
   [ 1. GENERATE ]  [ 2. MODIFY ]  [ 3. VALIDATE ]   [ 4. RESUME ]
         |                |               |                |
   Create from      Load source     Evaluate map     Continue from
   audio + timing   .osu + apply    against rules,   last verified
   or references    deltas into     audio, and       artifact in
   to new candidate isolated file   references       run directory
```

### 2.1 Mode `generate`
- **Objective**: Generate a complete `.osu` standard beatmap from audio input, user timing (BPM + offset), style profile, and target star rating.
- **Pre-conditions**: Valid audio file path, positive BPM, integer offset, target star range (`min` <= `max`), target style profile.
- **Generation Method**:
  1. *Rhythm Pass*: Timing grid alignment, density mapping, section division, rhythm anchor placement.
  2. *Geometry Pass*: Playfield coordinate placement (512x384), jump structures, slider shapes, flow angle momentum, stacking.
- **Artifacts**: New candidate `.osu` in `work/mapping-runs/<run-id>/candidate/`, `provenance.json`, `completion-report.json`.

### 2.2 Mode `modify`
- **Objective**: Apply targeted modifications (e.g., re-timing, difficulty re-scaling, pattern adjustments, hit-sound polishing) to an existing `.osu` beatmap.
- **Pre-conditions**: `source_beatmap_path` must exist and parse cleanly. `preserve_source: true` is strictly enforced.
- **Rules**: Never overwrite the source beatmap file. Produce a new candidate file in the unique run directory. Retain source metadata unless explicit modifications were requested.

### 2.3 Mode `validate`
- **Objective**: Perform automated static and dynamic validation on an existing or candidate `.osu` file without modifying it.
- **Pre-conditions**: Beatmap path, optional audio path for coverage, optional reference maps for similarity analysis.
- **Checks**: File format integrity, timing point hierarchy, beat-grid snapping, playfield boundary containment, coverage calculation, difficulty spike analysis, and originality against references.

### 2.4 Mode `resume`
- **Objective**: Recover an interrupted run (`INCOMPLETE`) without re-executing already verified stages.
- **Rules**: Verify integrity of existing artifacts against their recorded SHA-256 checksums in `provenance.json`. If valid, resume execution from the first incomplete stage.

---

## 3. Input Validation Rules

Before any mapping operation begins, all inputs in `mapping-brief.json` must be strictly validated:

1. **Ruleset & Mode**:
   - `ruleset` must be `"osu"` (osu!standard, Mode 0). Taiko (1), Catch (2), and Mania (3) are rejected in MVP.
   - `mode` must be one of `"generate"`, `"modify"`, `"validate"`, `"resume"`.

2. **Audio & Timing Integrity**:
   - `audio_path`: Must be a readable file path if song coverage validation is required.
   - `bpm`: Must be a positive floating-point number (`bpm > 0`).
   - `offset_ms`: Must be an integer representing millisecond offset of the first beat downbeat.
   - `target_star`: `min` and `max` must satisfy `0.5 <= target_star.min <= target_star.max <= 10.0`.

3. **Reference Integrity**:
   - If `require_originality_resolution: true` is set, at least one valid reference `.osu` must be supplied.
   - API references must be fetched safely without storing tokens or passwords in workspace logs.
   - Reference maps are used strictly for aggregate statistical distributions (spacing, density, angle distributions).

4. **Path Canonicalization & Safety Constraints**:
   - All input/output paths must be normalized to absolute paths.
   - Directory traversal (`..`), path tampering, junction/symlink escape outside `work/mapping-runs/<run-id>` is strictly forbidden.
   - Writing to system directories, user root, `.claude/skills/`, `.opencode/agents/`, or `.env` files is blocked.

---

## 4. Output Artifact Contracts

Every run must produce standardized artifacts under `work/mapping-runs/<run-id>/`:

```
work/mapping-runs/<run-id>/
├── input/
│   └── mapping-brief.json       # Normalized brief
├── plan/
│   └── mapping-plan.json        # Architect planning contract
├── candidate/
│   └── candidate.osu            # Generated/modified beatmap
├── reports/
│   ├── provenance.json          # Execution manifest & SHA-256 hashes
│   ├── completion-report.json   # Builder stage summary & status
│   └── verification-report.json # Verifier independent evaluation
└── logs/
    └── run.log                  # Structured, redacted execution logs
```

### 4.1 Required Artifacts and Roles

| Artifact | Producer | Consumer | Purpose |
|---|---|---|---|
| `mapping-plan.json` | Student Architect | Student Builder, Verifier | Locks scope, facts, assumptions, and acceptance criteria |
| `candidate.osu` | Student Builder | Student Verifier | Target osu! beatmap file |
| `provenance.json` | Student Builder | Student Verifier, Teacher | Records environment, scripts, tool inputs, and SHA-256 hashes |
| `completion-report.json` | Student Builder | Student Verifier, Teacher | Records generation metrics, coverage, and initial self-checks |
| `verification-report.json` | Student Verifier | Student Documenter, Teacher | Independent verification verdict, test logs, criterion states |

*Detailed JSON schemas are defined in `references/artifact-contract.md`.*

---

## 5. Originality Policy & Anti-Plagiarism Gates

To guarantee creative integrity and prevent plagiarism of existing beatmaps:

1. **Hard Anti-Copying Rules**:
   - **No Sequence Copying**: No consecutive sequence of more than 4 hit objects (circles, sliders, spinners) may copy identical rhythm timing and coordinate placement from any reference.
   - **No Rhythm Foundation Theft**: The candidate's rhythm timeline must be independently generated from audio analysis or timing rules, not ripped directly from reference timestamps.

2. **Originality Verdicts**:
   - `ORIGINAL`: No substantial pattern or sequence overlap detected. (PASSED)
   - `DERIVATIVE`: Shares aggregate style distributions or motif concepts but maintains independent rhythm and geometry. (PASSED with metric evidence)
   - `NEAR_CLONE`: Substantial sequence/timing duplication (>10% identical sequences). (**BLOCKED / FAILED**)
   - `CLONE`: Exact or near-exact replication of reference beatmap. (**BLOCKED / FAILED**)
   - `INCONCLUSIVE`: Reference data insufficient or unreadable to establish originality verdict. (**NOT A PASS / BLOCKED**)

*For calculation formulas and similarity thresholds, see `references/originality-policy.md`.*

---

## 6. Safety & Integrity Constraints

1. **Playfield Coordinate Boundaries**:
   - Playfield bounds: X from `0` to `512`, Y from `0` to `384`.
   - Hit circle centers and slider anchor points must remain within `[0, 512]` x `[0, 384]`.
   - Appropriate border padding (minimum 16 osupixels) is required to prevent hit circles from clipping outside screen edges under standard circle sizes (CS 3.5 - 5.0).

2. **Beat-Grid & Timing Snapping**:
   - Every hit object `time` must snap precisely to standard divisor intervals (1/1, 1/2, 1/3, 1/4, 1/6, 1/8) determined by active timing points.
   - Off-grid floating millisecond errors cause immediate validation failure.

3. **Source Immutability**:
   - Source audio files and original beatmaps must be treated as strictly read-only.
   - Global Claude skills (`C:\Users\PC SERANG 01\.claude\skills\...`) must never be modified.

4. **Secret Redaction**:
   - Never read, write, or echo `.env` files, API secrets, OAuth access tokens, or private user credentials in logs, plans, or reports.

---

## 7. Completion Criteria & Verdict Gates

A mapping run is declared `COMPLETE` by the Teacher if and only if all of the following conditions are satisfied:

- [x] **Artifact Existence**: `mapping-plan.json`, `candidate.osu`, `provenance.json`, `completion-report.json`, and `verification-report.json` exist and match their schema contracts.
- [x] **SHA-256 Consistency**: Source files retain original checksums; all candidate artifacts match hashes in `provenance.json`.
- [x] **Verifier Verdict**: `verification-report.json` status is `PASS`.
- [x] **File Integrity**: Beatmap passes all structural `.osu` parser tests without syntax or section errors.
- [x] **Song Coverage**: Candidate covers at least **95%** of the active song duration (when `require_full_song_coverage: true`).
- [x] **Originality Gate**: Originality verdict is `ORIGINAL` or `DERIVATIVE` (neither `CLONE`, `NEAR_CLONE`, nor `INCONCLUSIVE`).
- [x] **Difficulty Target**: Estimated Star Rating falls within `[target_star.min, target_star.max]`.
- [x] **Human Playability Boundary**: The Documenter handoff must explicitly state:
  > *"Automated static, geometry, and originality validation passed. Human gameplay feel, ergonomic strain, and modding readiness require manual playtesting in osu!."*

If any single hard check fails or remains inconclusive, the Teacher must output `INCOMPLETE` or `FAILED` with specific deficiency details.

---

## 8. Reference Documents

For detailed technical references, consult the companion guides:
- [osu! File Format Specification](references/osu_file_format.md)
- [Mapping Style Taxonomy & Pattern Catalog](references/style_taxonomy.md)
- [Originality Policy & Similarity Engine](references/originality-policy.md)
- [Classroom Artifact Protocol & Schemas](references/artifact-contract.md)
