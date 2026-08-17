"""Search: BM25 + dense → RRF k=60 → top-K."""
from __future__ import annotations

import logging
import sys
from collections import defaultdict

from .config import DEFAULT_TOP_K, RRF_K
from . import store

log = logging.getLogger(__name__)
# All logs go to stderr — MCP stdio must keep stdout clean for JSON-RPC.
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")


def rrf_fuse(bm25: list[tuple[str, float]], dense: list[tuple[str, float]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score = sum_r 1/(k + rank_r)."""
    scores: dict[str, float] = defaultdict(float)
    for rank, (cid, _) in enumerate(bm25, start=1):
        scores[cid] += 1.0 / (k + rank)
    for rank, (cid, _) in enumerate(dense, start=1):
        scores[cid] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


def search(
    query: str,
    *,
    k: int = DEFAULT_TOP_K,
    mode: str = "hybrid",
    query_vec: list[float] | None = None,
) -> list[dict]:
    """Search the active generation.

    mode ∈ {"hybrid", "bm25", "dense"}. For "hybrid", `query_vec` is required.
    """
    from .embed import encode_queries  # local import to avoid loading ONNX until needed

    con = store.open_active()
    if con is None:
        return []

    try:
        bm25 = []
        dense = []
        if mode in ("hybrid", "bm25"):
            bm25 = store.search_bm25(con, query)
        if mode in ("hybrid", "dense"):
            if query_vec is None:
                query_vec = encode_queries([query])[0]
            dense = store.search_vec(con, query_vec)

        if mode == "bm25":
            fused = [(cid, sc) for cid, sc in bm25[:k]]
        elif mode == "dense":
            fused = [(cid, sc) for cid, sc in dense[:k]]
        else:
            fused = rrf_fuse(bm25, dense)[:k]

        ids = [cid for cid, _ in fused]
        meta = store.fetch_chunks_meta(con, ids)
        out = []
        for cid, score in fused:
            m = meta.get(cid)
            if m is None:
                continue
            text = m["chunk_text"]
            snippet = (text[:240] + "…") if len(text) > 240 else text
            out.append({
                "id": cid,
                "doc_path": m["doc_path"],
                "doc_title": m["doc_title"],
                "category": m["category"],
                "heading_path": m["heading_path"] or "",
                "lifecycle": m["lifecycle"],
                "base_confidence": m["base_confidence"],
                "weight": m["weight"],
                "snippet": snippet,
                "score": round(float(score), 6),
                "match_sources": _match_sources(cid, bm25, dense),
            })
        return out
    finally:
        con.close()


def _match_sources(cid: str, bm25: list, dense: list) -> list[str]:
    sources = []
    if any(cid == x[0] for x in bm25):
        sources.append("bm25")
    if any(cid == x[0] for x in dense):
        sources.append("dense")
    return sources