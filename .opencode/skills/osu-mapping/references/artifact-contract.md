# Classroom Artifact Protocol & Contract Specification

This document defines the strict artifact protocols, JSON schemas, checksum requirements, and stage handoffs between MultiAI Classroom agents for beatmap generation runs.

---

## 1. Lifecycle & Directory Layout

Every mapping task is executed inside an isolated run directory identified by a unique `run-id` (e.g. `run-20260915-001` or UUID).

```
work/mapping-runs/<run-id>/
├── input/
│   └── mapping-brief.json          # Initial normalized input brief
├── plan/
│   └── mapping-plan.json           # Produced by Student Architect
├── candidate/
│   └── candidate.osu               # Produced by Student Builder
├── reports/
│   ├── provenance.json             # Produced by Student Builder
│   ├── completion-report.json      # Produced by Student Builder / Validator
│   └── verification-report.json    # Produced by Student Verifier
└── logs/
    └── run.log                     # Sanitized execution and audit trail
```

---

## 2. Checksum & Immutability Requirements

1. **SHA-256 Everywhere**: Every source file, referenced beatmap, execution script, generated candidate `.osu`, and report artifact must have its SHA-256 hash calculated and logged.
2. **Source Immutability Assertion**: The SHA-256 hash of `source_beatmap_path` and `audio_path` recorded at the beginning of the run must match exactly at the end of the run:
   $$\text{SHA256}(\text{source}_{\text{start}}) == \text{SHA256}(\text{source}_{\text{end}})$$
3. **Artifact Integrity**: Student Verifier must re-calculate hashes of all files in `candidate/` and `plan/` to confirm they match `provenance.json` before executing tests.

---

## 3. Artifact Schemas

### 3.1 `mapping-plan.json`
*Produced by Student Architect. Read-only contract for Student Builder & Verifier.*

```json
{
  "$schema": "https://opencode.ai/schemas/mapping-plan.schema.json",
  "run_id": "run-20260915-001",
  "mode": "generate",
  "normalized_input": {
    "audio_path": "C:/workspace/work/audio/song.mp3",
    "source_beatmap_path": null,
    "bpm": 180.0,
    "offset_ms": 1250,
    "target_star": { "min": 5.2, "max": 5.7 },
    "style": "flow_aim",
    "output_root": "C:/workspace/work/mapping-runs/run-20260915-001",
    "constraints": {
      "preserve_source": true,
      "overwrite": false,
      "require_full_song_coverage": true,
      "require_originality_resolution": true
    }
  },
  "facts_vs_assumptions": {
    "facts": [
      "Audio duration is 184500 ms",
      "Single uninherited timing point at 1250 ms with BPM 180.0",
      "Style requested is flow_aim at 5.2 - 5.7 stars"
    ],
    "assumptions": [
      "Standard 4/4 meter throughout the track",
      "Chorus sections located at 45000ms and 115000ms"
    ]
  },
  "timing_source": {
    "source_type": "user_provided",
    "bpm": 180.0,
    "offset_ms": 1250,
    "confidence": 1.0
  },
  "reference_targets": {
    "local_reference_paths": [
      "C:/workspace/references/example_flow_map.osu"
    ],
    "mapper_reference": null
  },
  "style_profile": {
    "style": "flow_aim",
    "target_star": { "min": 5.2, "max": 5.7 },
    "recommended_cs": 4.0,
    "recommended_ar": 9.3,
    "recommended_od": 9.0,
    "recommended_hp": 5.5,
    "base_slider_multiplier": 1.5
  },
  "execution_steps": [
    { "step": 1, "name": "Rhythm Generation", "tool": "osu_map_generate", "pass": "rhythm" },
    { "step": 2, "name": "Geometry Generation", "tool": "osu_map_generate", "pass": "geometry" },
    { "step": 3, "name": "Self-Validation", "tool": "osu_map_validate" },
    { "step": 4, "name": "Originality Gate", "tool": "osu_map_originality" }
  ],
  "expected_artifacts": [
    "candidate/candidate.osu",
    "reports/provenance.json",
    "reports/completion-report.json"
  ],
  "acceptance_criteria": [
    { "id": "AC-01", "description": "Candidate .osu passes parser integrity without syntax errors" },
    { "id": "AC-02", "description": "100% of hit objects snap to 1/1, 1/2, 1/3, or 1/4 divisors" },
    { "id": "AC-03", "description": "Song coverage >= 95.0%" },
    { "id": "AC-04", "description": "Star rating falls within 5.2 - 5.7 band" },
    { "id": "AC-05", "description": "Originality verdict is ORIGINAL or DERIVATIVE" }
  ],
  "blocking_questions": []
}
```

---

### 3.2 `provenance.json`
*Produced by Student Builder. Records reproducible environment, script checksums, and execution trace.*

```json
{
  "$schema": "https://opencode.ai/schemas/provenance.schema.json",
  "run_id": "run-20260915-001",
  "timestamp_start": "2026-09-15T10:00:00Z",
  "timestamp_end": "2026-09-15T10:02:15Z",
  "opencode_version": "1.18.30",
  "python_version": "3.11.8",
  "environment": {
    "os": "win32",
    "platform": "Windows 10 Pro"
  },
  "agent_signatures": {
    "architect": "student-architect",
    "builder": "student-builder",
    "verifier": null,
    "documenter": null
  },
  "scripts_manifest": [
    {
      "name": "generate_osu.py",
      "path": "C:/workspace/.opencode/skills/osu-mapping/scripts/generate_osu.py",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    },
    {
      "name": "validate_osu.py",
      "path": "C:/workspace/.opencode/skills/osu-mapping/scripts/validate_osu.py",
      "sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a"
    }
  ],
  "inputs_manifest": [
    {
      "type": "audio",
      "path": "C:/workspace/work/audio/song.mp3",
      "sha256": "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
    },
    {
      "type": "reference",
      "path": "C:/workspace/references/example_flow_map.osu",
      "sha256": "a35b0b4b204e12e128103328e14e1a065b741daae41793741ef03cb2acba24ae"
    }
  ],
  "candidate_manifest": {
    "path": "C:/workspace/work/mapping-runs/run-20260915-001/candidate/candidate.osu",
    "sha256": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
  },
  "tool_invocations": [
    {
      "tool": "osu_map_generate",
      "arguments_sanitized": {
        "mapping_plan_path": "C:/workspace/work/mapping-runs/run-20260915-001/plan/mapping-plan.json",
        "run_directory": "C:/workspace/work/mapping-runs/run-20260915-001"
      },
      "exit_code": 0
    }
  ]
}
```

---

### 3.3 `completion-report.json`
*Produced by Student Builder / Validation tool. Summarizes generation metrics and self-check results.*

```json
{
  "$schema": "https://opencode.ai/schemas/completion-report.schema.json",
  "run_id": "run-20260915-001",
  "mode": "generate",
  "status": "COMPLETE",
  "output_beatmap_path": "C:/workspace/work/mapping-runs/run-20260915-001/candidate/candidate.osu",
  "format_version": 14,
  "ruleset": "osu",
  "object_counts": {
    "circles": 420,
    "sliders": 210,
    "spinners": 2,
    "total": 632
  },
  "song_coverage_percent": 97.4,
  "estimated_difficulty": {
    "star_rating": 5.42,
    "aim_rating": 2.85,
    "speed_rating": 2.57,
    "target_band_min": 5.2,
    "target_band_max": 5.7,
    "matches_target": true
  },
  "stage_results": {
    "file_integrity": "PASS",
    "beat_grid_validity": "PASS",
    "song_coverage": "PASS",
    "target_difficulty": "PASS",
    "style_heuristics": "PASS",
    "originality_gate": "PASS"
  },
  "originality": {
    "verdict": "ORIGINAL",
    "sequence_match_fraction": 0.0,
    "rhythm_jaccard": 0.28
  },
  "skipped_checks": [],
  "hard_requirements_passed": true,
  "warnings": [],
  "errors": []
}
```

---

### 3.4 `verification-report.json`
*Produced by Student Verifier. Independent evaluation of criteria and candidate files.*

```json
{
  "$schema": "https://opencode.ai/schemas/verification-report.schema.json",
  "run_id": "run-20260915-001",
  "timestamp": "2026-09-15T10:05:00Z",
  "verifier_id": "student-verifier",
  "verdict": "PASS",
  "acceptance_criteria_results": [
    {
      "id": "AC-01",
      "description": "Candidate .osu passes parser integrity without syntax errors",
      "status": "PASS",
      "evidence": "Parser parsed 632 objects, 12 timing points, 0 syntax warnings."
    },
    {
      "id": "AC-02",
      "description": "100% of hit objects snap to 1/1, 1/2, 1/3, or 1/4 divisors",
      "status": "PASS",
      "evidence": "All 632 objects snapped to valid grid ticks."
    },
    {
      "id": "AC-03",
      "description": "Song coverage >= 95.0%",
      "status": "PASS",
      "evidence": "Active mapped range 1250ms - 181200ms represents 97.4% coverage."
    },
    {
      "id": "AC-04",
      "description": "Star rating falls within 5.2 - 5.7 band",
      "status": "PASS",
      "evidence": "Computed SR = 5.42* (Aim: 2.85, Speed: 2.57)."
    },
    {
      "id": "AC-05",
      "description": "Originality verdict is ORIGINAL or DERIVATIVE",
      "status": "PASS",
      "evidence": "Verdict: ORIGINAL (F_match=0.0, max consecutive matching=2)."
    }
  ],
  "commands_executed": [
    {
      "command": "python .opencode/skills/osu-mapping/scripts/validate_osu.py --candidate work/mapping-runs/run-20260915-001/candidate/candidate.osu --audio work/audio/song.mp3",
      "exit_code": 0,
      "stdout_snippet": "Validation complete: 0 errors, 0 warnings. Overall: PASS"
    }
  ],
  "integrity_checks": {
    "source_unchanged": true,
    "candidate_exists": true,
    "sha256_matches_provenance": true
  },
  "regressions_detected": false,
  "blocker_details": [],
  "playability_disclaimer": "Automated static, geometry, and originality validation passed. Human gameplay feel, ergonomic strain, and modding readiness require manual playtesting in osu!."
}
```
