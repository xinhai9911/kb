# Module 14: Python Tools

**LLM**: deepseek-v3.2 | **Model**: gpt-5.3-codex-2 | **Tools**: find, rg, edit, read, write

---

## What It Covers

The Python ecosystem in llama.cpp — the GGUF Python package, conversion/quantization scripts, and Python API bindings for inference. Provides Python-first tooling for model manipulation and inference.

## Key Concepts

### GGUF Python Package (`gguf-py`)
- **Installation**: `pip install -e gguf-py/` (local dev) or from PyPI
- **Reader**: Load and inspect GGUF files from Python
- **Writer**: Create and modify GGUF files programmatically
- **Scripts**: Command-line utilities for GGUF manipulation

### GGUF Scripts
| Script | Purpose |
|--------|---------|
| `gguf-dump` | Display GGUF file metadata and structure |
| `gguf-set-metadata` | Modify metadata fields in a GGUF file |
| `gguf-convert-endian` | Convert endianness of GGUF tensors |
| `gguf-new-metadata` | Create new metadata for a GGUF file |
| `gguf-editor-gui` | GUI editor for GGUF files (requires tkinter) |

### Python API / Bindings
- `llama_cpp` Python package (separate from main repo) provides Python bindings
- Used in various examples: `train-text-from-scratch`, embedding workflows
- Enables Python-first development and scripting

## Files

| Directory | Purpose |
|-----------|---------|
| `gguf-py/` | GGUF Python package source |
| `gguf-py/gguf/` | Core GGUF Python library |
| `gguf-py/README.md` | GGUF package documentation |

## Usage Guidance

1. Install: `pip install -e gguf-py/` (for local development)
2. Use `gguf-dump` to inspect model files: `gguf-dump model.gguf`
3. Modify metadata: `gguf-set-metadata model.gguf key value`
4. Convert endianness for cross-platform compatibility
5. Use Python API for scripted model workflows

## Cross-Module Links

- **06-tensor-gguf**: GGUF format specification, `gguf-py/gguf/` — the Python implementation of GGUF format
- **05-model-api**: Model loading in C++ (Python GGUF tools complement this)
- **08-examples**: Several examples use the Python GGUF package for model conversion
- **07-grammars**: Grammar files are pure-text and don't use Python tools directly
