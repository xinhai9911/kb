"""Markdown chunker — frontmatter-aware, H2/H3-splitting.

Strategy:
  1. Read file, strip UTF-8 BOM if present.
  2. Parse YAML frontmatter (PyYAML).
  3. Walk markdown-it tokens; flush a chunk at every H2/H3 boundary.
  4. Safety split: if a chunk exceeds MAX_CHUNK_CHARS, split at paragraph breaks.

Each chunk record carries enough metadata for ranking and display:
  id, doc_path, doc_title, category, heading_path, chunk_idx, chunk_text,
  lifecycle, base_confidence, tags, mtime_ns, size, weight.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterator

import yaml
from markdown_it import MarkdownIt

from .config import MAX_CHUNK_CHARS, PARAGRAPH_OVERLAP_CHARS, SYSTEM_PAGES

_BOM = "﻿"


def _strip_bom(text: str) -> str:
    return text.lstrip(_BOM) if text.startswith(_BOM) else text


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text).

    Recognises a leading YAML block delimited by --- lines. Returns ({}, text)
    if no frontmatter is present.
    """
    text = _strip_bom(text)
    if not text.startswith("---"):
        return {}, text
    # Find the closing ---
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_text = "".join(lines[1:end])
    body = "".join(lines[end + 1 :])
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        fm = {}
    if not isinstance(fm, dict):
        fm = {}
    return fm, body


def _make_md() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "breaks": False})
    return md


def _inline_to_text(tokens: list, start: int) -> tuple[str, int]:
    """Walk inline tokens starting at `start` until the matching close; return (text, next_idx)."""
    parts: list[str] = []
    i = start
    while i < len(tokens):
        tok = tokens[i]
        ttype = tok.type
        if ttype == "inline":
            parts.append(tok.content)
            i += 1
        elif ttype.endswith("_open"):
            inner, next_i = _inline_to_text(tokens, i + 1)
            parts.append(inner)
            i = next_i
        elif ttype.endswith("_close"):
            return "".join(parts), i + 1
        else:
            # text or softbreak/hr etc.
            if ttype == "text":
                parts.append(tok.content)
            i += 1
    return "".join(parts), i


def _collect_block_text(tokens: list, start: int) -> tuple[str, int]:
    """Collect plain text from a block-level token until its close."""
    parts: list[str] = []
    i = start
    while i < len(tokens):
        tok = tokens[i]
        if tok.type.endswith("_open"):
            inner, next_i = _collect_block_text(tokens, i + 1)
            parts.append(inner)
            i = next_i
        elif tok.type.endswith("_close"):
            return "\n".join(p for p in parts if p), i + 1
        elif tok.type == "inline":
            parts.append(tok.content)
            i += 1
        elif tok.type in {"text", "fence", "code_block"}:
            if tok.type in {"fence", "code_block"}:
                # Keep code blocks but mark them — useful for retrieval on code-heavy pages.
                lang = tok.info.split()[0] if tok.info else ""
                parts.append(f"```{lang}\n{tok.content}\n```")
            else:
                parts.append(tok.content)
            i += 1
        else:
            i += 1
    return "\n".join(p for p in parts if p), i


def _walk_tokens(tokens: list) -> Iterator[tuple[str, str]]:
    """Yield (level, heading_text) for each heading found.

    level is 'h2' or 'h3'.
    """
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            tag = tok.tag  # 'h2' or 'h3'
            inline_tok = tokens[i + 1]
            text = inline_tok.content if inline_tok.type == "inline" else ""
            if tag in {"h2", "h3"}:
                yield tag, text.strip()
            i += 3  # open, inline, close
            continue
        i += 1


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split text that's still too long at paragraph boundaries."""
    if len(text) <= max_chars:
        return [text]
    paragraphs = text.split("\n\n")
    out: list[str] = []
    buf = ""
    for p in paragraphs:
        if not p.strip():
            continue
        if len(buf) + len(p) + 2 > max_chars:
            if buf.strip():
                out.append(buf.strip())
            # Hard-truncate ultra-long single paragraph
            if len(p) > max_chars:
                # Slice with overlap
                for j in range(0, len(p), max_chars - overlap):
                    out.append(p[j : j + max_chars])
                buf = ""
            else:
                buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf.strip():
        out.append(buf.strip())
    return out


def chunk_file(path: Path) -> list[dict]:
    """Return a list of chunk records for the given md file."""
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    md = _make_md()
    tokens = md.parse(body)

    doc_title = fm.get("title") or path.stem
    category = fm.get("category")
    lifecycle = fm.get("lifecycle")
    base_confidence = fm.get("base_confidence")
    tags = fm.get("tags") or []
    is_system = path.name in SYSTEM_PAGES
    weight = 0.3 if is_system else 1.0

    # Walk blocks: collect (heading_path, paragraph_text) for non-heading blocks.
    blocks: list[tuple[str, str]] = []  # (heading_path, block_text)
    cur_h2 = ""
    cur_h3 = ""
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            tag = tok.tag
            inline_tok = tokens[i + 1]
            heading_text = (inline_tok.content if inline_tok.type == "inline" else "").strip()
            if tag == "h2":
                cur_h2 = heading_text
                cur_h3 = ""
            elif tag == "h3":
                cur_h3 = heading_text
            i += 3
            continue
        if tok.type in {"paragraph_open", "fence", "code_block", "blockquote_open", "bullet_list_open", "ordered_list_open", "table_open"}:
            block_text, next_i = _collect_block_text(tokens, i + 1)
            heading_path = ("## " + cur_h2) if cur_h2 else ""
            if cur_h3:
                heading_path = (heading_path + " > ### " + cur_h3) if heading_path else ("### " + cur_h3)
            if block_text.strip():
                blocks.append((heading_path, block_text))
            i = next_i + 1 if next_i > i else i + 1
            continue
        i += 1

    # Build chunks by heading path; sub-chunks split on length.
    by_heading: dict[str, list[str]] = {}
    for heading_path, block_text in blocks:
        if not block_text.strip():
            continue
        sub = _split_long(block_text, MAX_CHUNK_CHARS, PARAGRAPH_OVERLAP_CHARS)
        for s in sub:
            by_heading.setdefault(heading_path, []).append(s)

    chunks: list[dict] = []
    doc_rel = str(path).replace("\\", "/")
    for heading_path, texts in by_heading.items():
        joined = "\n\n".join(texts).strip()
        if not joined:
            continue
        chunk_id = hashlib.sha1(f"{doc_rel}|{heading_path}".encode("utf-8")).hexdigest()[:16]
        chunks.append({
            "id": chunk_id,
            "doc_path": doc_rel,
            "doc_title": doc_title,
            "category": category,
            "heading_path": heading_path,
            "chunk_idx": 0,
            "chunk_text": joined,
            "lifecycle": lifecycle,
            "base_confidence": float(base_confidence) if isinstance(base_confidence, (int, float)) else None,
            "tags": json_list(tags),
            "weight": weight,
        })

    # Re-number chunk_idx per file in document order.
    for idx, c in enumerate(chunks):
        c["chunk_idx"] = idx

    return chunks


def json_list(x) -> str:
    import json
    if isinstance(x, list):
        return json.dumps(x, ensure_ascii=False)
    return ""