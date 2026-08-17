"""Indexer: walk vault → chunk → embed → atomic generation swap.

Uses mtime + size as the cheap change detector. Stores per-file state in
INDEX_DIR/state.json. On the very first run (no state.json), performs a
full rebuild.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

from . import chunker, embed, store
from .config import EXCLUDE_DIRS, VAULT_PATH, INDEX_DIR

log = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")


def _state_path() -> Path:
    return INDEX_DIR / "state.json"


def _load_state() -> dict:
    p = _state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    _state_path().write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _walk_vault(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # In-place prune — never descend into excluded dirs.
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            if f.lower().endswith(".md"):
                out.append(Path(dirpath) / f)
    return out


def _stat(path: Path) -> tuple[int, int]:
    st = path.stat()
    return int(st.st_mtime_ns), int(st.st_size)


def _changed_or_new(path: Path, state: dict, force: bool) -> bool:
    if force:
        return True
    rel = str(path).replace("\\", "/")
    cur = _stat(path)
    prev = state.get(rel)
    if prev is None:
        return True
    return (cur[0] != prev.get("mtime_ns")) or (cur[1] != prev.get("size"))


def update(*, force: bool = False) -> str:
    """Run an incremental (or full, with force=True) rebuild. Returns new generation id."""
    t0 = time.time()
    state = _load_state()
    files = _walk_vault(VAULT_PATH)
    log.info(f"walked {len(files)} md files under {VAULT_PATH}")

    changed_files = [f for f in files if _changed_or_new(f, state, force)]
    unchanged_count = len(files) - len(changed_files)
    log.info(f"changed/new: {len(changed_files)}, unchanged: {unchanged_count}")

    all_chunks: list[dict] = []
    for fp in changed_files:
        try:
            chunks = chunker.chunk_file(fp)
        except Exception as e:
            log.warning(f"chunk failed for {fp}: {e}")
            continue
        mtime_ns, size = _stat(fp)
        rel = str(fp).replace("\\", "/")
        for c in chunks:
            c["mtime_ns"] = mtime_ns
            c["size"] = size
            c["doc_path"] = rel
        all_chunks.extend(chunks)
        log.info(f"  {rel}: {len(chunks)} chunks")

    if not all_chunks and not force:
        log.info("nothing to do; index already up-to-date")
        return store.active_generation_id() or ""

    # Embed the changed chunks (bge-small-zh-v1.5 lazy-loads here on first call).
    log.info(f"encoding {len(all_chunks)} chunks with bge-small-zh…")
    t_enc0 = time.time()
    texts = [c["chunk_text"] for c in all_chunks]
    embeddings = embed.encode_passages(texts)
    log.info(f"  done in {time.time() - t_enc0:.1f}s")

    # For unchanged files, copy chunks from the previous generation. This keeps
    # the new generation complete (every active file represented) without
    # re-encoding anything that didn't change.
    log.info("merging unchanged chunks from previous generation…")
    unchanged_chunks: list[dict] = []
    unchanged_embeddings: list[list[float]] = []
    prev_gid = store.active_generation_id()
    if prev_gid:
        prev_db = store.generation_path(prev_gid) / "index.db"
        if prev_db.exists():
            prev_con = store.open_db(prev_db)
            try:
                prev_chunks = prev_con.execute(
                    """
                    SELECT id, doc_path, doc_title, category, heading_path, chunk_idx,
                           chunk_text, lifecycle, base_confidence, tags, weight
                    FROM chunks
                    """
                ).fetchall()
                prev_changed_paths = {c["doc_path"] for c in all_chunks}
                for r in prev_chunks:
                    if r["doc_path"] in prev_changed_paths:
                        continue
                    cid = r["id"]
                    row = prev_con.execute(
                        "SELECT embedding FROM chunks_vec WHERE id = ?", (cid,)
                    ).fetchone()
                    if row is None:
                        continue
                    raw = row["embedding"]
                    # sqlite-vec returns the float32 buffer; deserialize.
                    import struct
                    n = len(raw) // 4
                    floats = list(struct.unpack(f"{n}f", raw))
                    unchanged_chunks.append(dict(r))
                    unchanged_embeddings.append(floats)
            finally:
                prev_con.close()

    final_chunks = all_chunks + unchanged_chunks
    final_embeddings = embeddings + unchanged_embeddings
    log.info(f"writing new generation with {len(final_chunks)} chunks "
             f"({len(all_chunks)} new/changed + {len(unchanged_chunks)} copied)")

    gen_id, db_path = store.write_generation(final_chunks, final_embeddings)
    store.activate(gen_id)

    # Update state with the mtime/size of all files (changed + unchanged).
    new_state = dict(state)
    for fp in files:
        rel = str(fp).replace("\\", "/")
        try:
            mtime_ns, size = _stat(fp)
            new_state[rel] = {"mtime_ns": mtime_ns, "size": size}
        except OSError:
            pass
    # Drop entries for files that no longer exist.
    files_set = {str(p).replace("\\", "/") for p in files}
    for k in list(new_state.keys()):
        if k not in files_set:
            del new_state[k]
    _save_state(new_state)

    log.info(f"generation {gen_id} active at {db_path} ({time.time() - t0:.1f}s total)")
    return gen_id