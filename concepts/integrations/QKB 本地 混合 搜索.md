---
aliases: ["qkb-local-hybrid-search"]
title: qkb 本地混合检索（已落地）
category: concepts
tags: [ai-agent, rag, information-retrieval, embedding, search, tooling, hybrid-retrieval]
created: 2026-08-03
updated: 2026-08-03
summary: qkb 是为本 vault 量身定制的本地混合检索工具：BM25（FTS5）+ bge-small-zh-v1.5（ONNX CPU）+ RRF k=60，全部跑在本地，零外部 API；提供 CLI / MCP（Claude Code 集成）/ HTTP 三种接口
base_confidence: 0.85
lifecycle: reviewed
lifecycle_changed: 2026-08-03
sources: []
---

# qkb 本地混合检索（已落地）

## 一句话定义

**qkb** = `Q:\AI\kb\qkb\` Python 包 + `~\.kb-index\` 索引目录。给定 vault 路径 → 切片 → 编码 → 写入 sqlite-vec+FTS5 → 提供 CLI/MCP/HTTP 三种方式跑 BM25+bge-small-zh-v1.5+RRF 混合检索。

## 它在解决什么问题

vault 已 329+ md 文件，wiki-query 是基于 frontmatter + 关键词 + wikilink 的"结构化检索"，但有两个盲区：

1. **语义召回弱** —— 用户写"摄影构图"想找的不只是命中字面词的页，还包括讲"三分法/引导线/对称"但没写"构图"二字的页
2. **跨域概念发现差** —— "Transformer" 既在 AI 也在 video editing 的上下文里出现，关键词检索难分权重

qkb 的设计目标是补这两个洞，同时**完全本地**——零 API 费用、零数据出网。

## 架构

```
vault md files (329 个, ~1.9 MB)
    │
    │  chunker.py: strip frontmatter → markdown-it H2/H3 split → ~1200 char chunks
    ▼
chunks (1045 个, 平均 ~600 字)
    │
    │  embed.py: bge-small-zh-v1.5 ONNX, 'passage:' prefix, mean-pool, L2-norm
    ▼
1024-dim float32 vectors (1045 × 512 × 4B ≈ 2 MB)
    │
    │  store.py: write_generation → generations/NNNN/index.db
    ▼
┌────────────────────────────────────────┐
│ index.db (sqlite-vec 0.1.9 + FTS5)     │
│   chunks     (TEXT PK, metadata)        │
│   chunks_vec (vec0 float[512])          │
│   chunks_fts (fts5 unicode61)           │
│   + 3 triggers keep chunks_fts synced   │
└────────────────────────────────────────┘

search (RRF k=60):
    query → BM25 top-50 + Dense top-100 → RRF → top-30
```

## 选型回顾（v1 实际产出）

| 维度 | 计划 | 实际 | 原因 |
|---|---|---|---|
| Embedding | bge-m3 (1024-dim) | **bge-small-zh-v1.5 (512-dim)** | fastembed 不支持 bge-m3；bge-small-zh 是同系列中文优化版且更小更快 |
| embedding 库 | fastembed | **onnxruntime + tokenizers 直接调** | huggingface.co 在本机 SSL 不可达，HF mirror xet 401；改走 Qdrant fastembed CDN 拉 tarball |
| 存储 | sqlite-vec + FTS5 | 同 | 单文件、无 daemon、足够 |
| 融合 | RRF k=60 | 同 | spec 锁定 |
| 接口 | CLI + MCP + HTTP | 同 | 三个都验证过 |

## 关键工程决定

### 1. 完全脱离 fastembed / huggingface_hub

本机无法访问 `huggingface.co`（SSL handshake timeout），HF mirror 的 xet 重构端点返回 401。绕道方案：

- fastembed 在 metadata 里登记了 `https://storage.googleapis.com/qdrant-fastembed/` URL（实测可达）
- 但 fastembed 实际只走 `snapshot_download`（HF），URL 字段没生效
- 所以**直接用 `onnxruntime.InferenceSession` + `tokenizers.Tokenizer` 加载本地 ONNX**

`qkb setup` 子命令从 Qdrant CDN 拉 `fast-bge-small-zh-v1.5.tar.gz` (~55 MB)，解压到 `~/.cache/qkb/fast-bge-small-zh-v1.5/`。**首次 setup 后所有推理离线**。

### 2. BGE FlagEmbedding 风格 prefix

`bge-small-zh-v1.5` 训练时对文档加 `passage:` 前缀、对查询加 `query:` 前缀（`bge-m3` 同理）。不加前缀召回下降 10–15%。代码里硬编码：

```python
# embed.py
prefixed = [f"passage: {t}" for t in texts]  # encode_passages
prefixed = [f"query: {t}" for t in texts]    # encode_queries
```

### 3. mean-pool + L2-normalize

`hidden_size=512`，输出 `last_hidden_state` 形状 `[N, seq, 512]`。attention-mask 加权求和再除以 token 数（mask 防 pad 干扰）。BGE 论文明示最后要 L2-normalize，cosine similarity = dot product。

### 4. SQLite load_extension 必须先 enable

Python `sqlite3` 默认禁 `load_extension`（`not authorized`）。修复：在 `sqlite_vec.load(con)` 前加 `con.enable_load_extension(True)`。

### 5. FTS5 用 trigger 自动同步

FTS5 `content='chunks'` 模式下要通过 trigger 同步：

```sql
CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, chunk_text, doc_title, heading_path)
  VALUES (new.rowid, new.chunk_text, new.doc_title, new.heading_path);
END;
```

主表 INSERT chunks 后 trigger 自动写 FTS index。BM25 查询用 `chunks_fts JOIN chunks ON chunks.rowid = chunks_fts.rowid` 把 FTS5 rowid 翻译回 chunks.id。

> ⚠️ **不要用 FTS5 STORED 列**：SQLite 内置 FTS5 不支持 `STORED` 关键字（那是 `fts5-icu` 之类的扩展）。独立 `chunks_fts` + trigger 模式是标准做法。

### 6. ONNX 内存与 batch_size

`bge-small-zh` 用了 optimized-ONNX graph。**单次 batch=8 + max_length=256 + 动态 padding** 才能在 16 GB 内存机上跑。早期用 max_length=512、batch=32，单次请求 9 GB 直接 OOM。

```python
# embed.py
def _batch_encode(texts, max_length=256):
    _tokenizer.enable_truncation(max_length=max_length)
    encs = _tokenizer.encode_batch(texts)
    max_len = min(max_length, max(len(e.ids) for e in encs))
    _tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=max_len)
    encs = _tokenizer.encode_batch(texts)
    ...
```

### 7. 排除 `test-data/`

vault 顶层有 `test-data/zhangsan/`（个人真实数据：身份证、学籍、工作、家庭）。**默认不索引**——`config.EXCLUDE_DIRS` 里显式列出。如果未来需要检索示例数据再放开。

## 三种接口

### CLI

```bash
cd Q:/AI/kb
python -m qkb setup                    # 下载 bge-small-zh 模型到 ~/.cache/qkb/
python -m qkb update                   # 全量/增量重建索引
python -m qkb update --full            # 强制全量
python -m qkb status                   # 当前 generation / chunk 数 / db size
python -m qkb search "摄影构图" -k 5   # 混合检索
python -m qkb search "RRF" --mode bm25 # 仅 BM25
python -m qkb search "..." --mode dense # 仅向量
python -m qkb serve --http             # 启 FastAPI 在 127.0.0.1:8765
python -m qkb serve --mcp              # 启 MCP stdio
```

### MCP（Claude Code 集成）

注册在 `~/.claude.json` 的 `mcpServers.qkb`：

```json
{
  "command": "python",
  "args": ["-m", "qkb.mcp_server"],
  "cwd": "Q:/AI/kb"
}
```

暴露一个 tool：

```python
@mcp.tool()
def search(query: str, k: int = 10, mode: str = "hybrid") -> list[dict]:
    """Hybrid retrieval over the local vault."""
```

在 Claude Code 里直接说"用 qkb 找关于 X 的笔记"会触发。

### HTTP

`POST /search {"query":"...", "k":10, "mode":"hybrid"}` → `{"results": [...], "count": N}`。

`GET /health` → `{"ok": true, "generation": "0001"}`

`GET /stats` → `{"generation", "model", "chunks", "files"}`

## 性能数据（实测）

| 操作 | 实测耗时 | 备注 |
|---|---|---|
| `qkb setup` 首次 | ~3 s | 下载 55 MB tarball |
| `qkb update` 全量（1045 chunks）| **~25 s** | 22 s encode + 3 s DB 写入 |
| `qkb update` 增量（1 文件）| < 2 s | mtime 比对 |
| 冷启动 + 首次 search | ~3 s | ONNX runtime + tokenizer 加载 |
| Warm search（单 query）| **~150 ms** | BM25 ~5 ms + encode ~80 ms + vec ~30 ms + RRF <1 ms |
| DB 大小 | **~8 MB** | 1045 chunks × 512 × 4 B + FTS5 index |

## 怎么使用

1. 改 vault 任何文件后 → `cd Q:/AI/kb && python -m qkb update`
2. 想看效果 → `python -m qkb search "..." -k 5`
3. 在 Obsidian 里要"相关笔记" → 装 Smart Connections（独立于 qkb；后者给 Claude Code 和脚本用）
4. v2 路线（已留接口但未实现）：cross-encoder rerank、bge-m3 替代小 zh、jieba 中文分词替代 unicode61

## Related

- [[concepts/混合 检索 bm 25 语义 融合|关键词检索（BM25）+ 语义检索双路，融合排序]] —— qkb 的设计 spec
- [[concepts/Transformer 架构|Transformer 架构]] —— bge 模型底层
- [[concepts/智能体 内存 规划|Agent 记忆与规划]] —— RAG / 长期记忆的工程实现
- [[concepts/MCP 协议|Model Context Protocol]] —— qkb 暴露 tool 给 Claude Code 的协议层
- `Q:\AI\kb\qkb\` —— 源码（11 个文件，~800 行）
- `C:\Users\DELL\.kb-index\` —— 索引数据（gitignore）
- `C:\Users\DELL\.cache\qkb\fast-bge-small-zh-v1.5\` —— ONNX 模型（~95 MB）