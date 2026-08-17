"""MCP stdio server — exposes `search(query, k)` as a tool to Claude Code."""
from __future__ import annotations

import logging
import sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
log = logging.getLogger("qkb.mcp")

from mcp.server.fastmcp import FastMCP

from . import search

mcp = FastMCP("qkb")


@mcp.tool()
def search(query: str, k: int = 10, mode: str = "hybrid") -> list[dict]:
    """Hybrid retrieval over the local vault (BM25 + bge-m3 + RRF).

    Args:
        query: natural-language question or keywords.
        k: number of hits to return (default 10).
        mode: 'hybrid' (default), 'bm25', or 'dense'.

    Returns:
        List of {doc_path, doc_title, heading_path, snippet, score, match_sources}.
    """
    return search.search(query, k=k, mode=mode)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()