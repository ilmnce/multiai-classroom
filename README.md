# MultiAI Classroom MVP

OpenCode is the harness. `teacher` is the primary agent; five specialist Students handle planning, implementation, verification, cleanup, and documentation. OmniRoute supplies the models through localhost only.

## Current model routes

- Teacher: `omniroute/freemium`, a priority/fallback combo that currently includes Claude and GPT-class models.
- Students: `omniroute/classroom-students`, a multi-model combo with the shared Fable behavioral system instruction. The selected upstream may vary per request.

The upstream selected by a combo can change with availability. Provider status is not proof of a successful request, so use the smoke test before real work.

## Run

From PowerShell:

```powershell
cd 'C:\Users\PC SERANG 01\.omniroute\multiai-classroom'
& '.\Start-Classroom.ps1'
```

Then paste a PRD or ask Teacher to read one, for example:

```text
Read examples/sample-prd.md and execute it for this repository. Use the full classroom flow.
```

One-shot mode in the Classroom repository:

```powershell
& '.\Start-Classroom.ps1' -Prompt 'Read examples/sample-prd.md and execute it. Use the full classroom flow.'
```

Run Classroom against another repository without copying its agent files:

```powershell
& '.\Start-Classroom.ps1' -Project 'C:\path\to\target-repo'
```

The launcher uses OpenCode's custom config and config-directory environment variables for that child process, so the Classroom provider and agents remain available while the working directory is the target repository. Existing project-specific OpenCode settings may still override matching provider/default settings according to OpenCode precedence.

Static discovery plus live provider smoke test:

```powershell
& '.\scripts\Test-Classroom.ps1'
```

Full Teacher-to-five-Students orchestration smoke test:

```powershell
& '.\scripts\Test-Classroom.ps1' -Live
```

## How dependency handoff works

OpenCode's `task` tool returns each Student's output to Teacher. Teacher must paste the concrete output into the dependent Student prompt under a labeled handoff section. A full mutation flow is Architect -> Builder -> Verifier -> Teacher verification -> Cleanup -> Documenter -> Teacher synthesis. Independent tasks may be delegated separately, but Teacher must still review decisive evidence before synthesis.

The registry at `registry/students.json` is deliberately simple and human-editable. Agent behavior and permissions live in `.opencode/agents/*.md`, which is the preferred project-local OpenCode structure for the installed 1.18.x line.

## Safety boundaries

- The launcher keeps the API key in the child process environment and restores the previous value on exit.
- No plaintext key is stored in this project.
- Sharing is disabled.
- Teacher has full authority over the user-scoped project and performs the final verification.
- Architect and Verifier are read-only. Builder, Cleanup, and Documenter can edit only when Teacher delegates an exact scope.
- Students may handle `.env`, credential configuration, or explicitly named external local paths only when Teacher authorizes that exact scope. Secret values must never be echoed, placed literally in command text, or returned in handoffs.
- Cleanup removes only scoped task artifacts and reports secret-history exposure. It does not silently erase active sessions, audit databases, backups, or unrelated logs.
- Lumiverse prompts and the `onlylumi` combo are not used by Classroom.

## MVP limitations

- Orchestration state lives in the OpenCode session; there is no separate queue, database, classroom UI, or retry scheduler yet.
- Dependency handoffs are prompt-mediated rather than a typed artifact protocol.
- The five Students share the `classroom-students` combo and differ by role prompt and permissions. The actual upstream is availability-dependent.
- Provider quota and tool-call reliability remain upstream-dependent.
