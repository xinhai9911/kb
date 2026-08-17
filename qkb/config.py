"""Configuration: paths, model, ranking constants.

All paths use forward slashes — Python's pathlib handles Windows correctly.
"""
from __future__ import annotations
import os
from pathlib import Path

# Vault root — the Obsidian vault we index.
VAULT_PATH = Path(os.environ.get("QKB_VAULT_PATH", "Q:/AI/kb")).resolve()

# Index root — outside the vault so it doesn't bloat git.
INDEX_DIR = Path(os.environ.get("QKB_INDEX_DIR", Path.home() / ".kb-index")).resolve()

# Embedding model — bge-small-zh-v1.5 (Chinese + English, 512-dim, ONNX CPU).
# Originally wanted BAAI/bge-m3 but fastembed does not support it; this is
# the closest fastembed-supported model with explicit Chinese optimization.
EMBEDDING_MODEL = os.environ.get("QKB_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
EMBEDDING_DIM = 512

# Local model directory — populated by `python -m qkb.cli setup` from the
# Qdrant fastembed CDN. Used directly by qkb.embed (no HF / fastembed dep).
MODEL_DIR = Path(os.environ.get(
    "QKB_MODEL_DIR",
    Path.home() / ".cache" / "qkb" / "fast-bge-small-zh-v1.5",
)).resolve()

# Ranking — RRF k=60; top-100 dense + top-50 BM25 → RRF → top-K (default 30).
RRF_K = 60
TOP_K_DENSE = 100
TOP_K_BM25 = 50
DEFAULT_TOP_K = 30

# HTTP server.
HTTP_HOST = "127.0.0.1"
HTTP_PORT = int(os.environ.get("QKB_HTTP_PORT", "8765"))

# Directories to exclude when walking the vault.
EXCLUDE_DIRS = frozenset({
    ".obsidian", ".git", ".remember", ".claude",
    "_raw", "_staging", "_archives", "_meta",
    "copilot", "Clippings", "Excalidraw", "scripts", ".github",
    "40-ideas", "90-archive", "journal", "references", "skills",
    # Sensitive test fixtures — names like zhangsan carry PII.
    "test-data",
})

# Files to mark as system pages (down-weighted in v2 rerank; v1 just records weight=0.3).
SYSTEM_PAGES = frozenset({"README.md", "index.md", "hot.md", "log.md"})

# Chunker parameters.
MAX_CHUNK_CHARS = 1200          # ~400 tokens; safe under bge-m3 8K context
PARAGRAPH_OVERLAP_CHARS = 100