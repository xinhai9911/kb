"""FastAPI HTTP server — POST /search, GET /health, GET /stats."""
from __future__ import annotations

import logging
import sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")

from fastapi import FastAPI
from pydantic import BaseModel

from . import search, store
from .config import DEFAULT_TOP_K, EMBEDDING_MODEL, HTTP_HOST, HTTP_PORT

app = FastAPI(title="qkb", version="0.1.0")


class SearchRequest(BaseModel):
    query: str
    k: int = DEFAULT_TOP_K
    mode: str = "hybrid"


@app.get("/health")
def health() -> dict:
    gid = store.active_generation_id()
    return {"ok": True, "generation": gid}


@app.get("/stats")
def stats() -> dict:
    gid = store.active_generation_id()
    con = store.open_active()
    chunks = 0
    files = 0
    if con is not None:
        try:
            chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            files = con.execute("SELECT COUNT(DISTINCT doc_path) FROM chunks").fetchone()[0]
        finally:
            con.close()
    return {
        "generation": gid,
        "model": EMBEDDING_MODEL,
        "chunks": chunks,
        "files": files,
    }


@app.post("/search")
def search_endpoint(req: SearchRequest) -> dict:
    results = search.search(req.query, k=req.k, mode=req.mode)
    return {"results": results, "count": len(results)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HTTP_HOST, port=HTTP_PORT, log_level="info")