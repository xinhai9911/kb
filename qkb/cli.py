"""CLI entry point — `python -m qkb.cli <subcommand> [...]`."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from . import indexer, search
from .config import DEFAULT_TOP_K, HTTP_HOST, HTTP_PORT, MODEL_DIR, EMBEDDING_MODEL
from . import store


MODEL_DOWNLOAD_URLS = {
    "BAAI/bge-small-zh-v1.5": "https://storage.googleapis.com/qdrant-fastembed/fast-bge-small-zh-v1.5.tar.gz",
}


def cmd_setup(args: argparse.Namespace) -> int:
    """Download the embedding model tarball into MODEL_DIR."""
    if MODEL_DIR.exists() and (MODEL_DIR / "model_optimized.onnx").exists():
        print(f"model already present at {MODEL_DIR}")
        return 0
    url = MODEL_DOWNLOAD_URLS.get(EMBEDDING_MODEL)
    if not url:
        print(f"no download URL known for {EMBEDDING_MODEL}", file=sys.stderr)
        return 1
    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url} ...")
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        with urllib.request.urlopen(url) as resp:
            shutil.copyfileobj(resp, tmp)
        tmp_path = Path(tmp.name)
    try:
        print(f"extracting to {MODEL_DIR} ...")
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tmp_path) as t:
            for member in t.getmembers():
                if not member.name.startswith("fast-bge-small-zh-v1.5/"):
                    continue
                rel = member.name.split("/", 1)[1] if "/" in member.name else member.name
                if not rel:
                    continue
                target = MODEL_DIR / rel
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("wb") as out:
                        src = t.extractfile(member)
                        if src is not None:
                            shutil.copyfileobj(src, out)
        print(f"ok — model at {MODEL_DIR}")
    finally:
        tmp_path.unlink(missing_ok=True)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    gen = indexer.update(force=args.full)
    print(f"active generation: {gen}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    results = search.search(args.query, k=args.k, mode=args.mode)
    if not results:
        print("(no results — try running `python -m qkb.cli update` first)")
        return 0
    out = []
    for r in results:
        title = r["doc_title"] or r["doc_path"]
        head = f"  [{r['heading_path']}]" if r["heading_path"] else ""
        sources = "/".join(r.get("match_sources") or [])
        out.append(
            f"{r['score']:.4f}  {r['doc_path']}{head}\n"
            f"        {title}   ({sources})\n"
            f"        {r['snippet']!r}"
        )
    print(f"== {len(results)} hits for: {args.query!r} (mode={args.mode}) ==\n")
    print("\n\n".join(out))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    gid = store.active_generation_id()
    print(f"active generation: {gid}")
    if not gid:
        print("no index yet — run `python -m qkb.cli update`")
        return 0
    p = store.current_db_path()
    if p:
        print(f"db: {p} ({p.stat().st_size // 1024} KiB)")
    con = store.open_active()
    if con is None:
        return 0
    try:
        n_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        n_files = con.execute("SELECT COUNT(DISTINCT doc_path) FROM chunks").fetchone()[0]
    finally:
        con.close()
    print(f"chunks: {n_chunks}, files: {n_files}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    if args.http:
        import uvicorn
        from .http_server import app
        uvicorn.run(app, host=HTTP_HOST, port=HTTP_PORT, log_level="info")
        return 0
    if args.mcp:
        from .mcp_server import main as mcp_main
        mcp_main()
        return 0
    print("specify --http or --mcp", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="qkb", description="local hybrid retrieval")
    sub = p.add_subparsers(dest="cmd", required=True)

    pu = sub.add_parser("update", help="build/refresh the index")
    pu.add_argument("--full", action="store_true", help="force a full rebuild")
    pu.set_defaults(func=cmd_update)

    ps = sub.add_parser("search", help="search the index")
    ps.add_argument("query")
    ps.add_argument("-k", type=int, default=DEFAULT_TOP_K)
    ps.add_argument("--mode", choices=["hybrid", "bm25", "dense"], default="hybrid")
    ps.set_defaults(func=cmd_search)

    pa = sub.add_parser("status", help="show index status")
    pa.set_defaults(func=cmd_status)

    psv = sub.add_parser("serve", help="start HTTP or MCP server")
    psv.add_argument("--http", action="store_true")
    psv.add_argument("--mcp", action="store_true")
    psv.set_defaults(func=cmd_serve)

    psetup = sub.add_parser("setup", help="download the embedding model")
    psetup.set_defaults(func=cmd_setup)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())