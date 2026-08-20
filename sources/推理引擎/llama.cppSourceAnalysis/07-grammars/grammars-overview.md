# Module 07: Grammars Overview

**LLM**: deepseek-v3.2 | **Model**: gpt-5.3-codex-2 | **Tools**: find, rg, edit, read, write

---

## What It Covers

The `grammars/` module implements GBNF (GGML BNF) grammars — a custom format for constrained grammar-based generation with llama.cpp. Grammars constrain LLM output to valid, pre-defined structures, preventing malformed or arbitrary responses.

## Key Concepts

### GBNF Format
- **Production rules**: Named rules that define valid output patterns
- **Terminal/non-terminal**: Terminals match literal strings; non-terminals reference other rules
- **Example** (from `grammars/README.md`):
  ```bnf
  root   ::= object
  value  ::= object | array | string | "true" | "false" | "null" | number
  object ::= "{" pair ("" ",\s* " pair)* "}"
  pair   ::= string ":" value
  number ::= [\-]? [0-9]+ [ \t]* ("\n" [\n])?
  ```

### How Grammars Work
- GBNF grammars **force** LLM output to match a grammar pattern — valid JSON, SQL, etc.
- Constrained generation happens at token-level: only tokens fitting the grammar are sampled
- Runtime engine is built into llama.cpp's inference pipeline

## Files

| File | Purpose |
|------|---------|
| `grammars/README.md` | Main documentation: GBNF format, rules, terminals, non-terminals |
| `grammars/` directory | Grammar examples and related files |

## Usage Guidance

1. Define a grammar for your use case (e.g., structured JSON output)
2. Pass the grammar file via `--grammar` / `-g` flag when calling `llama-cli`, `llama-server`, or using the library
3. For complex applications, combine with `grammar-file` option in API calls
4. Refer to `examples/` for grammar usage examples (e.g., JSON, SQL, etc.)

## Cross-Module Links

- **04-API/llama-server**: `--grammar` / `--grammar-file` options expose grammar support
- **05-model-api**: GBNF grammars use the same tokenization/sampling framework as the model
- **14-python/python-tools**: Grammar support in Python bindings and scripts
