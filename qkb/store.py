"""Storage layer — sqlite-vec + FTS5 in one file, atomic generation swap.

Schema:
  chunks        TEXT PK, full metadata
  chunks_vec    vec0 virtual table, 1024-dim float embeddings
  chunks_fts    fts5 virtual table (external content), BM25

We use atomic generation replacement: each update writes a fresh directory
under INDEX_DIR/generations/<NNNN>/, then INDEX_DIR/active.txt is rewritten
to point to it. Readers always open the path named in active.txt.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable

import sqlite_vec

from .config import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    INDEX_DIR,
    RRF_K,
    TOP_K_BM25,
    TOP_K_DENSE,
)


def index_dir() -> Path:
    return INDEX_DIR


def generations_dir() -> Path:
    return INDEX_DIR / "generations"


def active_generation_id() -> str | None:
    f = INDEX_DIR / "active.txt"
    if not f.exists():
        return None
    s = f.read_text().strip()
    return s or None


def generation_path(gen_id: str) -> Path:
    return generations_dir() / gen_id


def current_db_path() -> Path | None:
    gid = active_generation_id()
    if not gid:
        return None
    p = generation_path(gid) / "index.db"
    return p if p.exists() else None


def _next_generation_id() -> str:
    gdir = generations_dir()
    gdir.mkdir(parents=True, exist_ok=True)
    existing = sorted(p.name for p in gdir.iterdir() if p.is_dir())
    if not existing:
        return "0001"
    last = existing[-1]
    try:
        n = int(last)
        return f"{n + 1:04d}"
    except ValueError:
        return "0001"


def _create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS chunks (
          id TEXT PRIMARY KEY,
          doc_path TEXT NOT NULL,
          doc_title TEXT,
          category TEXT,
          heading_path TEXT,
          chunk_idx INTEGER,
          chunk_text TEXT NOT NULL,
          lifecycle TEXT,
          base_confidence REAL,
          tags TEXT,
          weight REAL DEFAULT 1.0
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
          id TEXT PRIMARY KEY,
          embedding float[{EMBEDDING_DIM}]
        );
        """
    )
    # FTS5 virtual table mirroring `chunks` (content='chunks', content_rowid='id').
    # FTS5 won't accept TEXT as content_rowid — we use rowid alias and rely on
    # the automatic INTEGER rowid on `chunks` (every INSERT without explicit
    # rowid gets a fresh INTEGER). For retrieval we look up chunks by joining
    # chunks_fts.rowid == chunks.rowid. To keep chunk_id stable across rebuilds
    # we instead expose chunk_text and join via doc_path+chunk_idx.
    con.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
          chunk_text, doc_title, heading_path,
          content='chunks', content_rowid='rowid',
          tokenize='unicode61 remove_diacritics 2'
        )
        """
    )
    # Triggers to keep chunks_fts in sync with chunks.
    con.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
          INSERT INTO chunks_fts(rowid, chunk_text, doc_title, heading_path)
          VALUES (new.rowid, new.chunk_text, new.doc_title, new.heading_path);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
          INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text, doc_title, heading_path)
          VALUES('delete', old.rowid, old.chunk_text, old.doc_title, old.heading_path);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
          INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text, doc_title, heading_path)
          VALUES('delete', old.rowid, old.chunk_text, old.doc_title, old.heading_path);
          INSERT INTO chunks_fts(rowid, chunk_text, doc_title, heading_path)
          VALUES (new.rowid, new.chunk_text, new.doc_title, new.heading_path);
        END;
        """
    )
    con.commit()


def open_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    # SQLite forbids load_extension by default; opt in first.
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    _create_schema(con)
    return con


def write_generation(
    chunks: Iterable[dict],
    embeddings: list[list[float]],
    *,
    previous_meta: dict | None = None,
) -> tuple[str, Path]:
    """Write a brand-new generation directory with the given chunks + embeddings.

    Returns (generation_id, db_path).
    """
    gen_id = _next_generation_id()
    gen_path = generation_path(gen_id)
    gen_path.mkdir(parents=True, exist_ok=True)
    db_path = gen_path / "index.db"

    chunks_list = list(chunks)
    assert len(chunks_list) == len(embeddings), "chunks / embeddings length mismatch"

    con = open_db(db_path)
    try:
        con.execute("BEGIN")
        for c, e in zip(chunks_list, embeddings):
            con.execute(
                """
                INSERT INTO chunks
                  (id, doc_path, doc_title, category, heading_path, chunk_idx,
                   chunk_text, lifecycle, base_confidence, tags, weight)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    c["id"], c["doc_path"], c.get("doc_title"),
                    c.get("category"), c.get("heading_path"), c.get("chunk_idx", 0),
                    c["chunk_text"], c.get("lifecycle"),
                    c.get("base_confidence"), c.get("tags", ""), c.get("weight", 1.0),
                ),
            )
            vec_blob = sqlite_vec.serialize_float32(e)
            con.execute(
                "INSERT INTO chunks_vec (id, embedding) VALUES (?, ?)",
                (c["id"], vec_blob),
            )
            # chunks_fts is auto-populated by the AFTER INSERT trigger.
        con.execute("COMMIT")

        manifest = {
            "generation": gen_id,
            "model": EMBEDDING_MODEL,
            "dim": EMBEDDING_DIM,
            "rrf_k": RRF_K,
            "chunks_count": len(chunks_list),
            "files_count": len({c["doc_path"] for c in chunks_list}),
        }
        (gen_path / "MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    finally:
        con.close()
    return gen_id, db_path


def activate(gen_id: str) -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / "active.txt").write_text(gen_id, encoding="utf-8")
    # Keep only the latest two generations for rollback safety.
    gdir = generations_dir()
    gens = sorted(p for p in gdir.iterdir() if p.is_dir())
    if len(gens) > 2:
        for old in gens[:-2]:
            shutil.rmtree(old, ignore_errors=True)


def open_active() -> sqlite3.Connection | None:
    p = current_db_path()
    if not p:
        return None
    return open_db(p)


def search_bm25(con: sqlite3.Connection, query: str, limit: int = TOP_K_BM25) -> list[tuple[str, float]]:
    """Return [(chunk_id, bm25_score), ...] ranked by BM25 (lower is better — we negate).

    Joins chunks_fts (which mirrors chunks via trigger) back to chunks.id
    so callers can use a stable TEXT id.
    """
    try:
        rows = con.execute(
            """
            SELECT c.id AS id, bm25(chunks_fts) AS s
            FROM chunks_fts
            JOIN chunks c ON c.rowid = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY s
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        like_q = f"%{query}%"
        rows = con.execute(
            """
            SELECT id AS id, 0.0 AS s
            FROM chunks
            WHERE chunk_text LIKE ?
            LIMIT ?
            """,
            (like_q, limit),
        ).fetchall()
    return [(r["id"], -float(r["s"])) for r in rows]


def search_vec(con: sqlite3.Connection, query_vec: list[float], limit: int = TOP_K_DENSE) -> list[tuple[str, float]]:
    """Return [(chunk_id, cosine_similarity), ...]."""
    qb = sqlite_vec.serialize_float32(query_vec)
    rows = con.execute(
        """
        SELECT id, vec_distance_cosine(embedding, ?) AS dist
        FROM chunks_vec
        ORDER BY dist
        LIMIT ?
        """,
        (qb, limit),
    ).fetchall()
    # cos distance: smaller is better. Convert to similarity in [0, 1] roughly.
    return [(r["id"], 1.0 - float(r["dist"])) for r in rows]


def fetch_chunks_meta(con: sqlite3.Connection, ids: list[str]) -> dict[str, sqlite3.Row]:
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = con.execute(
        f"SELECT id, doc_path, doc_title, category, heading_path, chunk_idx, "
        f"chunk_text, lifecycle, base_confidence, tags, weight "
        f"FROM chunks WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    return {r["id"]: r for r in rows}