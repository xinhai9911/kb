# Auto-Parser Architecture

## What Is the Auto-Parser

The auto-parser automatically analyzes Jinja chat templates to determine how to parse model outputs - including content, reasoning/thinking blocks, and tool calls - without requiring hardcoded per-model patterns.

## Core Philosophy

- **Minimize Hardcoded Patterns** - markers extracted through template comparison (only heuristic: JSON detection for `JSON_NATIVE` vs tag-based)
- **Compositional Architecture** - separate analyzer structs for reasoning, content, and tools

## Two-Step Process

1. `autoparser::autoparser(tmpl)` - runs all differential comparisons, populates analysis structs
2. `peg_generator::generate_parser(tmpl, params, analysis)` - builds a PEG parser and optional GBNF grammar

## How It Works: Differential Comparison

All analysis phases use a single comparison function:

```cpp
compare_variants(tmpl, params_A, params_modifier)
```

This renders the template twice (original vs modified), computes a diff with `prefix`, `suffix`, `left` (unique to A), `right` (unique to B), and extracts markers from the differences. Tag boundaries (`<...>`, `[...]`) are preserved during diff splitting.

## Analysis Phases

### Phase 1: Reasoning Analysis

| Check | What It Does |
|-------|-------------|
| R1: `compare_reasoning_presence()` | Message with vs without `reasoning_content` field |
| R2: `compare_thinking_enabled()` | `enable_thinking=false` vs `true` |
| R3: `compare_reasoning_scope()` | Reasoning+content vs reasoning+tools (tools-only detection) |

**Reasoning modes:**
- `NONE` - no reasoning markers
- `TAG_BASED` - e.g. `<think>...</think>`
- `TOOLS_ONLY` - reasoning only in tool call responses

### Phase 2: Content Analysis

Compares content-only output vs tool-call output and vs reasoning output.

**Content modes:**
- `PLAIN` - no content markers
- `ALWAYS_WRAPPED` - e.g. `<response>...</response>`
- `WRAPPED_WITH_REASONING` - wrapped only when reasoning present

### Phase 3: Tool Call Analysis

Skipped if `jinja_caps.supports_tool_calls` is false.

| Check | What It Does |
|-------|-------------|
| T1 | No-tools vs with-tools, classifies format |
| T2 | 1 call vs 2 calls, moves section to per-call markers |
| T3 | Two different function names, extracts name prefix/suffix |
| T4 | Argument name/value markers (TAG_WITH_TAGGED only) |
| T5 | 1 arg vs 2 args, finds separator |
| T6 | 0 args vs 1 arg, finds container markers |
| T7 | Call ID position and markers |

**Tool formats:**
- `JSON_NATIVE` - pure JSON: `{"name": "X", "arguments": {...}}`
- `TAG_WITH_JSON` - tag name + JSON args: `<function=X>{...}</function>`
- `TAG_WITH_TAGGED` - tag name + tag args: `<param=key>value</param>`

## Supported Models and Features

The auto-parser handles templates for: Llama 3.x, Qwen 2.5/3, DeepSeek R1/V3, Hermes 2/3, Mistral Nemo, Firefunction v2, Command R7B, Functionary v3.1/3.2, Granite 3.3/4.0, Phi, Gemma, and many more.

Specialized handlers exist for: GPT-OSS (channel-based), Functionary v3.2 (`>>>` delimiter), Ministral/Magistral Large 3.

## Parser Building

Each analyzer implements `build_parser()`:

| Component | Parser Strategy |
|-----------|----------------|
| Reasoning | `optional(start + reasoning(until(end)) + end)` |
| Content (PLAIN) | `reasoning + content(rest()) + end()` |
| Content (WRAPPED) | `start + content(until(end)) + end` |
| Tools (JSON) | Standard JSON tools with flat/nested/key dispatch |
| Tools (TAG_WITH_JSON) | Tag open + JSON schema + function close |
| Tools (TAG_WITH_TAGGED) | Per-argument string/JSON parsers with optional args |

## Entry Point

Invoked in `common/chat.cpp:1280-1310` inside `common_chat_templates_apply_jinja()`. A few specialized templates are handled first, then the auto-parser handles everything else.

## Files

| File | Purpose |
|------|---------|
| `common/chat-auto-parser.h` | All analysis structs, enums, generator |
| `common/chat-auto-parser-generator.cpp` | Parser generation |
| `common/chat-diff-analyzer.cpp` | Differential analysis and workarounds |
| `common/chat-auto-parser-helpers.h/cpp` | Diff split, segmentation, comparison helpers |
| `common/chat-peg-parser.h/cpp` | PEG builder, mapper, helpers |
| `common/chat.cpp` | Entry point |
| `tools/parser/debug-template-parser.cpp` | Debug tool |
| `tools/parser/template-analysis.cpp` | Template analysis tool |
