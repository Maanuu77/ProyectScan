# ADR-0005: Architecture documentation in three levels, exported as a zip

- Status: accepted
- Date: 2026-10-28

## Context

The first plan was an interactive dependency graph explained by an LLM. That is useful while exploring, but it cannot live in a README: GitHub renders static images, not interactive pages. The real goal is to help people understand how a project is organised from its README.

A single diagram does not work for real applications. Benchify, the reference project, has a Spring Boot backend with six hexagonal features and an Angular frontend; one picture with every class would be unreadable.

## Decision

Explain a project in three levels, each answering one question:

1. Overview: what is it made of (apps, databases, external services, deployment).
2. Features: what does it do (one card per business feature).
3. Flows: what happens when a user does something (frontend to database).

Plus a detail page per feature. Each diagram shows at most about nine elements and every element has a human-readable name.

The output is a zip with SVG and PNG diagrams (light and dark), Markdown pages and the raw analysis as JSON. The user decides what to copy into their repository; the tool does not edit their README.

## Consequences

- Readers get a short explanation first and depth on demand.
- Java and TypeScript support become required (see ADR-0007).
- Much more work than the original plan: layer classification, feature detection and HTTP linking between frontend and backend.
- No write access to the user's repository is needed, which keeps the tool safe and simple.
