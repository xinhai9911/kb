#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双向桥接 LLMForEverybody 外部文档与 vault 内部概念笔记。

Phase 1: 给每篇 LLMForEverybody 文章末尾添加「📚 相关概念」尾部链接
Phase 2: 给 vault 概念笔记添加「📖 来源参考」反向链接
Phase 3: 主索引添加 LLMForEverybody 入口
"""
import os, re, sys, json
from pathlib import Path
from collections import defaultdict

VAULT = Path(r"Q:\AI\kb")
LLM_DIR = VAULT / "sources" / "LLMForEverybody"

# ── Chapter → vault concept/entity/source mapping ──
CHAPTER_MAP = {
    "00": {
        "label": "AGI之路",
        "concepts": ["Transformer 架构", "LLM 评估 基准"],
        "entities": ["DeepSeek"],
        "sources": ["Vaswani 2017 Attention", "DeepSeek 4 技术"],
    },
    "01": {
        "label": "预训练",
        "concepts": ["Transformer 架构", "分词器 LLM", "LLM 训练 流水线",
                      "RLHF DPO 对齐", "LoRA PEFT 微调", "多模态 LLM",
                      "模型 压缩 蒸馏"],
        "entities": ["Hugging Face", "DeepSeek", "mindspore Transformer"],
        "sources": ["Vaswani 2017 Attention", "LLM 训练 流水线 指南",
                     "DeepSeek 4 技术"],
    },
    "02": {
        "label": "部署与推理",
        "concepts": ["LLM 推理 优化", "推测解码", "分布式推理",
                      "模型 压缩 蒸馏", "LLM 应用 生态"],
        "entities": ["vllm", "tensorrt-llm", "sglang", "Hugging Face"],
        "sources": ["LLM 推理 优化"],
    },
    "03": {
        "label": "微调",
        "concepts": ["LoRA PEFT 微调", "模型 压缩 蒸馏"],
        "entities": ["Hugging Face"],
    },
    "04": {
        "label": "量化",
        "concepts": ["模型 压缩 蒸馏", "分词器 LLM"],
    },
    "05": {
        "label": "显卡与并行",
        "concepts": ["分布式推理", "Transformer 架构"],
        "entities": ["Hugging Face"],
    },
    "06": {
        "label": "Prompt Engineering",
        "concepts": ["提示词 工程 模式", "AI 安全 对齐"],
    },
    "07": {
        "label": "Agent",
        "concepts": ["RAG 检索 增强 生成", "向量 DB 嵌入",
                      "混合 检索 bm 25 语义 融合", "智能体 编排 模式",
                      "智能体 编程", "智能体 工具 使用 MCP",
                      "智能体 长 期 内存", "多 智能体 协作",
                      "LLM 智能体 测试框架", "浏览器 智能体",
                      "轻量 智能体 框架", "LLM 应用 生态"],
        "entities": ["LangChain", "CrewAI", "Anthropic",
                      "OpenAI", "Google ADK"],
        "sources": ["Anthropic 智能体 构建", "LangChain 入门",
                     "MCP 规范", "智能体 框架 对比"],
    },
    "08": {
        "label": "企业落地",
        "concepts": ["AI 安全 对齐", "LLM 应用 生态"],
    },
    "09": {
        "label": "评估指标",
        "concepts": ["LLM 评估 基准", "智能体 评估 基准"],
    },
    "10": {
        "label": "热点",
        "concepts": ["AI 安全 对齐"],
    },
    "11": {
        "label": "数学",
        "concepts": ["Transformer 架构"],
    },
    "12": {
        "label": "企业与个人思考",
        "concepts": ["LLM 应用 生态"],
    },
}

# ── Path helpers ──

def detect_chapter(rel_path: str) -> str | None:
    """从相对路径提取章节号 (00-12)。"""
    for ch in ("00","01","02","03","04","05","06","07","08","09","10","11","12"):
        if rel_path.startswith(ch + "-") or f"/{ch}-" in rel_path:
            return ch
    return None

def build_link(name: str) -> str:
    """构建 wikilink。"""
    # Check which folder the concept lives in
    for folder in ("concepts", "entities", "sources", "synthesis"):
        fpath = VAULT / folder / f"{name}.md"
        if fpath.exists():
            return f"[[{folder}/{name}|{name}]]"
    return f"[[{name}]]"

def footer_already_present(content: str) -> bool:
    """检查是否已添加过相关概念尾部。"""
    return "📚 相关概念" in content or "📚 Related Concepts" in content

# ── Phase 1: Article → Vault links ──

def phase1_add_footers():
    """给每篇 LLMForEverybody 文章添加尾部链接。"""
    modified = 0
    skipped = 0
    errors = 0

    # Scan Chinese main content
    for chapter_dir in sorted(LLM_DIR.iterdir()):
        if not chapter_dir.is_dir():
            continue
        ch = detect_chapter(chapter_dir.name)
        if ch is None:
            continue
        mapping = CHAPTER_MAP.get(ch)
        if not mapping:
            continue

        for md_file in sorted(chapter_dir.rglob("*.md")):
            if md_file.name in ("索引.md", "README.md", "README 英.md", "README 俄.md"):
                continue
            try:
                rel = md_file.relative_to(LLM_DIR).as_posix()
                content = md_file.read_text(encoding="utf-8")

                if footer_already_present(content):
                    skipped += 1
                    continue

                # Build footer
                links = []
                for c in mapping.get("concepts", []):
                    links.append(build_link(c))
                for e in mapping.get("entities", []):
                    links.append(build_link(e))
                for s in mapping.get("sources", []):
                    links.append(build_link(s))

                if not links:
                    continue

                footer = f"\n\n---\n\n## 📚 相关概念\n\n"
                footer += " | ".join(links)
                footer += f"\n\n> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：{mapping['label']}\n"

                md_file.write_text(content + footer, encoding="utf-8")
                modified += 1
            except Exception as e:
                print(f"  ERROR: {md_file.relative_to(VAULT).as_posix()}: {e}")
                errors += 1

    # Scan docs/en/ and docs/ru/ (same chapter structure)
    for lang_dir in (LLM_DIR / "docs" / "en", LLM_DIR / "docs" / "ru"):
        if not lang_dir.exists():
            continue
        for chapter_dir in sorted(lang_dir.iterdir()):
            if not chapter_dir.is_dir():
                continue
            ch = detect_chapter(chapter_dir.name)
            if ch is None:
                continue
            mapping = CHAPTER_MAP.get(ch)
            if not mapping:
                continue

            for md_file in sorted(chapter_dir.rglob("*.md")):
                if md_file.name in ("索引.md", "README.md"):
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8")
                    if footer_already_present(content):
                        skipped += 1
                        continue

                    links = []
                    for c in mapping.get("concepts", []):
                        links.append(build_link(c))
                    for e in mapping.get("entities", []):
                        links.append(build_link(e))
                    for s in mapping.get("sources", []):
                        links.append(build_link(s))

                    if not links:
                        continue

                    footer = f"\n\n---\n\n## 📚 相关概念\n\n"
                    footer += " | ".join(links)
                    footer += f"\n\n> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：{mapping['label']}\n"

                    md_file.write_text(content + footer, encoding="utf-8")
                    modified += 1
                except Exception as e:
                    errors += 1

    print(f"Phase 1: modified={modified}, skipped(already has footer)={skipped}, errors={errors}")
    return modified

# ── Phase 2: Vault concept → article reverse links ──

def phase2_reverse_links():
    """给 vault 概念笔记添加反向链接到 LLMForEverybody 索引。"""
    # Collect which concepts have LLMForEverybody content
    concept_to_chapters = defaultdict(list)
    for ch, mapping in CHAPTER_MAP.items():
        for c in mapping.get("concepts", []):
            concept_to_chapters[c].append((ch, mapping["label"]))
        for e in mapping.get("entities", []):
            concept_to_chapters[e].append((ch, mapping["label"]))
        for s in mapping.get("sources", []):
            concept_to_chapters[s].append((ch, mapping["label"]))

    modified = 0
    for concept, chapters in concept_to_chapters.items():
        # Find the concept file
        target_file = None
        for folder in ("concepts", "entities", "sources", "synthesis"):
            fpath = VAULT / folder / f"{concept}.md"
            if fpath.exists():
                target_file = fpath
                break
        if not target_file:
            continue

        content = target_file.read_text(encoding="utf-8")
        if "📖 来源参考" in content or "LLMForEverybody" in content:
            continue  # already linked or has source reference

        # Build reverse link section
        unique_chapters = sorted(set(chapters), key=lambda x: x[0])
        chapter_links = []
        for ch, label in unique_chapters:
            chapter_links.append(f"[[sources/LLMForEverybody/索引#{label}|{label}（第{ch}章）]]")

        section = f"\n\n---\n\n## 📖 来源参考\n\n"
        section += f"- **LLMForEverybody**：{' / '.join(chapter_links)}\n"
        section += "> 来自 [luhengshiwo/LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody) 外部知识库导入\n"

        target_file.write_text(content + section, encoding="utf-8")
        modified += 1

    print(f"Phase 2: modified {modified} vault concept files with reverse links")
    return modified

# ── Phase 3: Main index → LLMForEverybody ──

def phase3_main_index():
    """在主索引中添加 LLMForEverybody 入口。"""
    index_file = VAULT / "索引.md"
    content = index_file.read_text(encoding="utf-8")

    if "LLMForEverybody" in content:
        print("Phase 3: main index already has LLMForEverybody entry, skip")
        return 0

    # Find a good insertion point - after AI 大模型 section
    marker = "## eBPF 内核可编程"
    if marker not in content:
        print("Phase 3: cannot find insertion point, skip")
        return 0

    insertion = f"""
## LLMForEverybody（外部知识库）

- [[sources/LLMForEverybody/索引|LLMForEverybody 导航总览（12 章 259 篇）]]
  > 来源：[luhengshiwo/LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)（中文大模型知识体系，含英/俄翻译本）

"""

    content = content.replace(marker, insertion + marker)
    index_file.write_text(content, encoding="utf-8")
    print("Phase 3: added LLMForEverybody entry to main index")
    return 1

# ── Main ──

if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print("=" * 60)
    print("LLMForEverybody <-> Vault bridge")
    print("=" * 60)

    print("\n--- Phase 1: Article → Vault concept links ---")
    p1 = phase1_add_footers()

    print("\n--- Phase 2: Vault concept → Article reverse links ---")
    p2 = phase2_reverse_links()

    print("\n--- Phase 3: Main index entry ---")
    p3 = phase3_main_index()

    print("\n" + "=" * 60)
    print(f"Done! Phase1={p1} Phase2={p2} Phase3={p3}")
    print("=" * 60)
