# Sample PRD: Project Health Summary

## Goal

Add a small, repository-local health summary for a project so a developer can quickly see how to install, test, and run it.

## Required outcome

- Inspect the target repository and identify its real install, test, and run commands.
- Add `docs/project-health.md` with those commands and the evidence used to derive them.
- Do not change application behavior.
- Verify every documented command that is safe to run locally.
- Report commands that cannot be verified and why.

## Suggested classroom flow

1. Architect maps package files, scripts, and current documentation.
2. Builder creates the health summary from the Architect handoff.
3. Verifier runs the documented commands and checks that the file matches reality.
4. Documenter tightens the final runbook using only the Verifier's evidence.
5. Teacher reconciles findings and reports the final status.
