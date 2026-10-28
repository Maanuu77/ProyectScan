# ADR-0001: Record architecture decisions

- Status: accepted
- Date: 2026-10-28

## Context

repo-xray is a portfolio project. Reviewers want to know why it is built the way it is, not only what it does. Decisions explained only in commit messages get lost.

## Decision

Record every significant technical decision as a short Architecture Decision Record in `docs/adr/`, numbered in order and based on `0000-template.md`. An ADR is never edited after it is accepted; a new ADR supersedes it.

## Consequences

- The README can link to the reasoning instead of repeating it.
- Writing an ADR takes a few minutes per decision.
