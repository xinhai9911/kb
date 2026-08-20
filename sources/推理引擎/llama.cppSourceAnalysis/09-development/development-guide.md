# Module 09: Development Guide

**LLM**: deepseek-v3.2 | **Model**: gpt-5.3-codex-2 | **Tools**: find, rg, edit, read, write

---

## What It Covers

The development workflow, contribution process, code quality standards, and contributor guidelines for llama.cpp. Includes the `CONTRIBUTING.md` guide and `AGENTS.md` AI-specific rules.

## Key Concepts

### Contribution Levels
- **Level 1**: First-time contributors — documentation, minor bug fixes
- **Level 2**: Regular contributors — features, non-trivial fixes
- **Level 3**: Maintainers — code review, merge authority

### PR Requirements
- New features require a clear description of **what** and **why**
- Code must follow the project style (C++11, minimal dependencies)
- Tests and documentation updates are expected for non-trivial changes
- Large PRs should be broken into smaller, reviewable chunks

### Code Quality
- No external dependencies — llama.cpp is self-contained
- C++11 standard with no STL beyond basic containers
- Compatibility with MSVC, GCC, Clang, and cross-platform targets (desktop, mobile, embedded)
- Linux CI with address/thread sanitizer checks

## Files

| File | Purpose |
|------|---------|
| `CONTRIBUTING.md` | Full contributor guide: PR process, code style, review rules |
| `AGENTS.md` | AI contributor rules: commit format, testing requirements, code quality |
| `SECURITY.md` | Security policy: vulnerability reporting, secure usage practices |
| `docs/development/` | Additional development docs (e.g., `HOWTO-add-model.md`) |
| `docs/development/HOWTO-add-model.md` | Step-by-step: adding a new model architecture to llama.cpp |

## How to Add a New Model

1. **Register model type** — define a new `MODEL_TYPE` enum entry and add to the registry
2. **Implement model architecture** — subclass `llm_arch` and fill in tensor mappings
3. **Add tensors** — define weight/parameter tensor names for the new architecture
4. **Update export/conversion** — add conversion scripts for your model format

## Usage Guidance

- Read `CONTRIBUTING.md` before submitting your first PR
- Follow the commit message format described in `AGENTS.md`
- Run CI checks locally before pushing: `./ci/run.sh`
- Check `SECURITY.md` for vulnerability disclosure procedures

## Cross-Module Links

- **04-API/llama-server**: Production code you may be contributing to
- **05-model-api**: `HOWTO-add-model.md` references the model loading framework
- **13-cicd**: `ci/run.sh` — local CI execution before submitting PRs
