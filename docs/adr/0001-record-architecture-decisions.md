# 1. Record Architecture Decisions

Date: 2026-10-04

## Status
Accepted

## Context
We need to record significant architectural, structural, and tooling decisions
made throughout the lifecycle of this project so humans and AI agents understand
the rationale behind key choices.

## Decision
We will use Architecture Decision Records (ADRs) stored in `docs/adr/`.
Each record describes:
- **Status**: Proposed, Accepted, Rejected, Superseded.
- **Context**: The problem or requirement prompting the decision.
- **Decision**: The selected option and why it was chosen.
- **Consequences**: Positive and negative outcomes or trade-offs.

## Consequences
- Every major architectural shift is tracked in version control.
- Agents reading this repository can inspect historical decisions to avoid
  re-proposing already evaluated or superseded designs.
