# OpenCode Multi-AI osu! Mapping Skill & Plugin (MVP)

A project-local capability in OpenCode that automates the planning, generation, modification, and verification of osu!standard (`.osu` v14) beatmaps using the MultiAI Classroom workflow.

---

## 1. What Was Added

- **Project-Local Skill (`osu-mapping`)**: Implements standard operating procedures, timing engine, two-pass generation (rhythm pass then geometry pass), pattern catalog (`aimslop`, `flow_aim`, `hybrid`), cursor simulation, and originality policy.
- **Typed Custom Tools (`osu_map_*`)**: Four schema-validated tools for OpenCode:
  - `osu_map_inspect`: Extracts metadata, timing points, difficulty settings, and hit object distributions from `.osu` files.
  - `osu_map_generate`: Generates playable `.osu` beatmaps into isolated run directories.
  - `osu_map_validate`: Enforces format integrity, beat-grid snapping, playfield bounds, and song coverage.
  - `osu_map_originality`: Computes $n$-gram matching, rhythm Jaccard index, and geometric correlation against reference maps.
- **Hardening Plugin (`osu-mapping-guard`)**: Lifecycle tracking (`PLANNED -> BUILDING -> VERIFYING -> COMPLETE`), path security guards, secret redaction, manifest verification, and recovery management.
- **Classroom Schemas**: JSON Schemas for `mapping-brief`, `mapping-plan`, `completion-report`, and `verification-report`.
- **Test Harness**: Standalone verification suite covering PRD Section 19 acceptance criteria.

---

## 2. Key Directories

```text
multiai-classroom/
├── .opencode/
│   ├── skills/osu-mapping/      # Skill instructions, references, and Python engine scripts
│   ├── tools/                   # Typed custom tools (osu-map-inspect, generate, validate, originality)
│   ├── plugins/                 # Hardening plugin (osu-mapping-guard.ts)
│   └── fixtures/                # Test fixtures (canonical-map, off-grid, self-reference, etc.)
├── schemas/                     # JSON Schemas governing artifact contracts
├── docs/                        # Architecture, testing, and handoff documentation
├── scripts/
│   └── test-osu-mapping.ps1     # Automated test harness & verification suite
└── work/
    └── mapping-runs/            # Isolated run directories (<run-id>/)
```

---

## 3. Quick Test

Run the full verification harness to validate all tools, security guards, and acceptance criteria:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test-osu-mapping.ps1
```

Or with PowerShell Core:

```powershell
pwsh scripts/test-osu-mapping.ps1
```

---

## 4. Status

- **Status**: **Project-Local Beta**
- **Milestones**: M0 (Baseline Audit), M1 (Project-Local Skill), M2 (Typed Tools), and M3 (Classroom Integration) are complete. Milestone M4 (Hardening Plugin) is implemented in preview.
- **Acceptance Criteria**: AC-01 through AC-14 verified. AC-15 (real-song live trial) is pending.

---

## 5. Next Steps

1. **Live Classroom E2E**: Execute full Teacher-to-four-Students orchestration flow using a live prompt in OpenCode.
2. **Real Dry Run (AC-15)**: Perform a full generation trial using a real local song audio file and community reference maps.
3. **Manual Playtesting**: Playtest generated `.osu` candidate beatmaps in osu! or osu!(lazer) to evaluate ergonomic flow and reading clarity.

---

## 6. Documentation References

- [User Handoff & Quick Start Guide](docs/osu-mapping-handoff.md)
- [Technical Architecture & Data Flow](docs/osu-mapping-architecture.md)
- [Test Strategy & Verification Suite](docs/osu-mapping-testing.md)
