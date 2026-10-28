# ADR-0003: Local LLM through Ollama

- Status: superseded by ADR-0011
- Date: 2026-10-28

## Context

Each node in the graph gets a plain-language explanation. The project must be free, and source code should not leave the user's machine.

## Decision

Use a small local model served by Ollama (default `qwen2.5-coder:3b`, configurable), called through its HTTP API. Use a low temperature, short answers and a prompt that only allows information present in the code. Cache each explanation by the hash of the code it explains.

## Consequences

- No API keys, no cost, and the code stays private.
- Explanations are slower and weaker than those of large hosted models; the cache and short prompts compensate.
- The rest of the tool must work when Ollama is not running: the graph is still generated and explanations are skipped with a clear message.
