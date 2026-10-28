# ADR-0007: tree-sitter for Java and TypeScript

- Status: accepted
- Date: 2026-10-28

## Context

The reference projects are written in Java (Spring Boot) and TypeScript (Angular, React). Python's `ast` only parses Python. Options:

- Regular expressions: fragile with generics, annotations and template strings.
- Each language's own compiler (javac, the TypeScript compiler): needs a JDK or Node.js on the user's machine, which beginners may not have.
- tree-sitter: one fast parsing library with prebuilt grammars on PyPI, no runtime needed and error-tolerant.

## Decision

Use `tree-sitter` with `tree-sitter-java` and `tree-sitter-typescript` (TS and TSX). Keep `ast` for Python (ADR-0002). Each parser produces the same language-neutral model, so everything after parsing is shared.

## Consequences

- Wheels are prebuilt for Windows, so the executable does not need a compiler.
- tree-sitter gives syntax only, not types: calls are resolved by name and imports, as with Python.
- Adding a language means adding one parser module.
