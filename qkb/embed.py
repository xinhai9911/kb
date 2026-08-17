"""Embedding wrapper — direct ONNX + tokenizers, no fastembed / HF dependency.

Why: the machine couldn't reach huggingface.co (SSL timeout) and HF mirror's
xet reconstruction returned 401. The Qdrant fastembed CDN at
storage.googleapis.com/qdrant-fastembed/ IS reachable, so we download the
tarball once into MODEL_DIR and load from disk.

Model: BAAI/bge-small-zh-v1.5 (BertModel, hidden_size=512, max_pos=512).
Prefix per FlagEmbedding style: 'passage: ' for docs, 'query: ' for queries.
Mean-pooled, L2-normalised embeddings.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from .config import EMBEDDING_DIM, MODEL_DIR

log = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")

_session: ort.InferenceSession | None = None
_tokenizer: Tokenizer | None = None


def _load() -> None:
    global _session, _tokenizer
    if _session is not None:
        return
    if not MODEL_DIR.exists():
        raise FileNotFoundError(
            f"model not found at {MODEL_DIR}. Run `python -m qkb.cli setup` first."
        )
    onnx_path = MODEL_DIR / "model_optimized.onnx"
    tokenizer_path = MODEL_DIR / "tokenizer.json"
    log.info(f"loading onnx model from {onnx_path}")
    so = ort.SessionOptions()
    so.intra_op_num_threads = 4
    # Keep default CPU memory arena conservative.
    _session = ort.InferenceSession(str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"])
    log.info(f"loading tokenizer from {tokenizer_path}")
    _tokenizer = Tokenizer.from_file(str(tokenizer_path))
    # No default padding/truncation; we set per-batch below.


def _batch_encode(texts: list[str], max_length: int = 256) -> np.ndarray:
    """Tokenize and run the ONNX model. Returns embeddings [N, 512].

    We deliberately keep `max_length` short (default 256) to keep the
    attention matrix tractable in CPU memory, and pad to the per-batch
    max length rather than a fixed max. Most wiki chunks fit in 256 tokens.
    """
    _load()
    # Per-batch dynamic truncation/padding.
    _tokenizer.enable_truncation(max_length=max_length)
    encs = _tokenizer.encode_batch(texts)
    # Find per-batch max len (cap at max_length, but allow shorter).
    if not encs:
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
    max_len = min(max_length, max(len(e.ids) for e in encs))
    _tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=max_len)
    encs = _tokenizer.encode_batch(texts)  # re-encode with the now-set padding length

    input_ids = np.array([e.ids for e in encs], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
    token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

    outputs = _session.run(
        None,
        {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        },
    )
    last_hidden = outputs[0]  # [N, seq, 512]
    mask = attention_mask[:, :, None].astype(np.float32)
    summed = (last_hidden * mask).sum(axis=1)
    counts = mask.sum(axis=1).clip(min=1e-9)
    embeddings = summed / counts
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True).clip(min=1e-9)
    embeddings = embeddings / norms
    return embeddings.astype(np.float32)


def encode_passages(texts: list[str], batch_size: int = 8) -> list[list[float]]:
    """Encode a list of document chunks in micro-batches."""
    if not texts:
        return []
    prefixed = [f"passage: {t}" for t in texts]
    out: list[list[float]] = []
    for i in range(0, len(prefixed), batch_size):
        batch = prefixed[i : i + batch_size]
        embs = _batch_encode(batch)
        out.extend(embs.tolist())
    return out


def encode_queries(texts: list[str], batch_size: int = 4) -> list[list[float]]:
    """Encode query strings in micro-batches."""
    if not texts:
        return []
    prefixed = [f"query: {t}" for t in texts]
    out: list[list[float]] = []
    for i in range(0, len(prefixed), batch_size):
        batch = prefixed[i : i + batch_size]
        embs = _batch_encode(batch)
        out.extend(embs.tolist())
    return out