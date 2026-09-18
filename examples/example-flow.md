# Example dependency flow

User prompt:

```text
Read examples/sample-prd.md and execute it for this repository. Use the full classroom flow.
```

Expected orchestration:

```text
PRD
  -> student-architect: plan + acceptance criteria
  -> student-builder: receives concrete Architect handoff, implements
  -> student-verifier: receives Architect + Builder handoffs, tests independently
  -> teacher: independently inspects decisive changes and evidence
  -> student-cleanup: removes scoped temporary artifacts and checks secret exposure
  -> student-documenter: receives verified post-cleanup facts, finalizes docs when needed
  -> teacher: reviews contradictions and synthesizes the result
```

Teacher should report which Students actually ran, what evidence each produced, and any work that remains unverified.
