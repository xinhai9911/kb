#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix scattered nodes: bridge isolated clusters and link orphans."""
import os, re, sys

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
VAULT = os.path.abspath(r"Q:\AI\kb")

def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return None

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def append_section(path, section_text):
    """Append a section to a file if not already present."""
    content = read_file(path)
    if content is None:
        return False
    # Check if section already exists
    if section_text.strip()[:30] in content:
        return False
    # Remove trailing whitespace/newlines
    content = content.rstrip() + "\n\n" + section_text + "\n"
    write_file(path, content)
    return True

changes = []

# ═══════════════════════════════════════════════════════
# 1. Fix HBase cluster (6 nodes) → bridge to main graph
# ═══════════════════════════════════════════════════════

# 1a. HBase.md → add link to project
hbase_main = os.path.join(VAULT, "20-protocols", "HBase.md")
c = read_file(hbase_main)
if c and "10-projects/数据库 解码器" not in c:
    c = c.rstrip() + "\n\n## 关联项目\n\n- [[10-projects/数据库 解码器|Database Decoder 工作流]] — HBase 解码器是该项目的已完成模块\n- [[projects/db-decoder-ironhive/解码器 轨道|解码器开发 Track]] — IronHive 解码器状态机\n"
    write_file(hbase_main, c)
    changes.append("HBase.md +project link")

# 1b. Each HBase sub-note → add back-link to HBase main + project
hbase_sub_notes = [
    ("20-protocols", "HBase 测试 计划.md"),
    ("20-protocols", "HBase 测试 执行.md"),
    ("20-protocols", "HBase 静态 分析.md"),
    ("20-protocols", "HBase 删除 表 包.md"),
    ("30-snippets", "HBase 测试 报告 模板.md"),
]
for folder, fname in hbase_sub_notes:
    fpath = os.path.join(VAULT, folder, fname)
    section = (
        "---\n\n## 🔗 关联\n\n"
        "- [[20-protocols/HBase|HBase 协议分析]] — 主协议页\n"
        "- [[10-projects/数据库 解码器|Database Decoder 工作流]] — 所属项目\n"
        "- [[projects/db-decoder-ironhive/解码器 轨道|解码器开发 Track]]"
    )
    if append_section(fpath, section):
        changes.append(f"{folder}/{fname} +back-link")

# 1c. Add HBase sub-notes to main index (they're missing!)
index_path = os.path.join(VAULT, "索引.md")
idx = read_file(index_path)
if idx and "HBase 删除 表 包" not in idx:
    # Find the HBase section and add sub-notes
    old = '- [[20-protocols/HBase 2|HBase 协议分析]]'
    new = (
        '- [[20-protocols/HBase 2|HBase 协议分析]]\n'
        '  - [[20-protocols/HBase 静态 分析|HBase TPR 字段静态分析]]\n'
        '  - [[20-protocols/HBase 删除 表 包|HBase dropTable 报文解析]]\n'
        '  - [[20-protocols/HBase 测试 计划|HBase 测试计划]]\n'
        '  - [[20-protocols/HBase 测试 执行|HBase 测试执行计划]]\n'
        '  - [[30-snippets/HBase 测试 报告 模板|HBase 测试报告模板]]'
    )
    idx = idx.replace(old, new)
    write_file(index_path, idx)
    changes.append("索引.md +HBase sub-notes")

# ═══════════════════════════════════════════════════════
# 2. Fix team-building cluster → bridge to main graph
# ═══════════════════════════════════════════════════════
# Add to index under a new section
idx = read_file(index_path)
if idx and "团队团建" not in idx:
    # Insert before ## 归档
    marker = "## 归档"
    section = (
        "## 团队管理\n\n"
        "- [[50-reference/团队团建五维复盘模板|团建/复盘模板]]\n"
        "- [[journal/团队团建活动总结报告|团建活动总结（示例草稿）]]\n\n"
    )
    idx = idx.replace(marker, section + marker)
    write_file(index_path, idx)
    changes.append("索引.md +team section")

# ═══════════════════════════════════════════════════════
# 3. Fix single-node orphans
# ═══════════════════════════════════════════════════════

# 3a. 20-protocols/模板 → link to protocol section
tmpl = os.path.join(VAULT, "20-protocols", "模板.md")
c = read_file(tmpl)
if c and "关联" not in c:
    c = c.rstrip() + "\n\n## 关联\n\n- [[10-projects/数据库 解码器|Database Decoder 工作流]] — 协议分析模板所属项目\n"
    write_file(tmpl, c)
    changes.append("20-protocols/模板.md +link")

# 3b. 30-snippets/模板 → link to snippets index
tmpl2 = os.path.join(VAULT, "30-snippets", "模板.md")
c = read_file(tmpl2)
if c and "片段 索引" not in c:
    c = c.rstrip() + "\n\n## 关联\n\n- [[30-snippets/片段 索引|片段索引]]\n"
    write_file(tmpl2, c)
    changes.append("30-snippets/模板.md +link")

# 3c. Clippings → add back-links
clipping_files = [
    "Clippings/【LLM】从零开始训练大模型.md",
    "Clippings/Understanding LangChain and LangGraph_ A Beginner's Guide to AI Workflows了解 LangChain 和 LangGraph：面向初学者的 AI 工作流程指南.md",
]
for cf in clipping_files:
    fpath = os.path.join(VAULT, cf)
    c = read_file(fpath)
    if c is None:
        continue
    if "关联" in c:
        continue
    # Determine topic
    if "LangChain" in cf:
        section = (
            "---\n\n## 🔗 关联\n\n"
            "- [[concepts/RAG 检索 增强 生成|RAG 检索增强生成]]\n"
            "- [[concepts/智能体 编排 模式|Agent 编排模式]]\n"
            "- [[entities/LangChain|LangChain]]\n"
            "- [[sources/LLMForEverybody/索引|LLMForEverybody 导航]]"
        )
    elif "LLM" in cf or "训练" in cf:
        section = (
            "---\n\n## 🔗 关联\n\n"
            "- [[concepts/LLM 训练 流水线|LLM 训练管线]]\n"
            "- [[concepts/Transformer 架构|Transformer 架构]]\n"
            "- [[sources/LLMForEverybody/索引|LLMForEverybody 导航]]"
        )
    else:
        continue
    if append_section(fpath, section):
        changes.append(f"Clippings/{os.path.basename(cf)[:20]}... +link")

# 3d. sources/LLM 推理 优化 → link to concept
src_inf = os.path.join(VAULT, "sources", "LLM 推理 优化.md")
c = read_file(src_inf)
if c and "关联" not in c:
    c = c.rstrip() + "\n\n## 🔗 关联\n\n- [[concepts/LLM 推理 优化|LLM 推理优化]] — 概念笔记\n- [[sources/LLMForEverybody/索引|LLMForEverybody 导航]] — 第二章「部署与推理」\n"
    write_file(src_inf, c)
    changes.append("sources/LLM 推理 优化.md +link")

# 3e. sources/LLMForEverybody READMEs → link to index
for readme in ["README 英.md", "README 俄.md"]:
    fpath = os.path.join(VAULT, "sources", "LLMForEverybody", readme)
    c = read_file(fpath)
    if c and "关联" not in c:
        c = c.rstrip() + "\n\n---\n\n## 🔗 关联\n\n- [[sources/LLMForEverybody/索引|LLMForEverybody 导航总览]]\n"
        write_file(fpath, c)
        changes.append(f"LLMForNobody/{readme[:10]}... +link")

# 3f. LLMForEverybody draft/翻译笔记 → link to index
for sub in ["docs/en/翻译 笔记", "docs/ru/翻译 笔记", "draft/md/模板"]:
    fpath = os.path.join(VAULT, "sources", "LLMForEverybody", sub + ".md")
    c = read_file(fpath)
    if c and "关联" not in c:
        c = c.rstrip() + "\n\n---\n\n## 🔗 关联\n\n- [[sources/LLMForEverybody/索引|LLMForEverybody 导航总览]]\n"
        write_file(fpath, c)
        changes.append(f"LLMForNobody/{sub[:20]}... +link")

# ═══════════════════════════════════════════════════════
# 4. Fix low-degree edge nodes
# ═══════════════════════════════════════════════════════

# 4a. 20-protocols/InfluxDB → add project link
influx = os.path.join(VAULT, "20-protocols", "InfluxDB.md")
c = read_file(influx)
if c and "10-projects/数据库 解码器" not in c:
    c = c.rstrip() + "\n\n## 关联项目\n\n- [[10-projects/数据库 解码器|Database Decoder 工作流]] — InfluxDB 解码器是该项目的已完成模块\n"
    write_file(influx, c)
    changes.append("InfluxDB.md +project link")

# 4b. 30-snippets/片段 索引 → add link to main index
snippets_idx = os.path.join(VAULT, "30-snippets", "片段 索引.md")
c = read_file(snippets_idx)
if c and "索引.md" not in c:
    c = c.rstrip() + "\n\n## 关联\n\n- [[索引|Wiki 主索引]]\n"
    write_file(snippets_idx, c)
    changes.append("片段 索引.md +link")

# 4c. projects/db-decoder-ironhive sub-notes → add project parent link
for sub_name in ["Hive 协议 分析", "Hive 解码器 实现"]:
    fpath = os.path.join(VAULT, "projects", "db-decoder-ironhive", sub_name + ".md")
    c = read_file(fpath)
    if c and "关联" not in c:
        c = c.rstrip() + "\n\n## 🔗 关联\n\n- [[projects/db-decoder-ironhive/DB 解码器 IronHive|项目概述]]\n- [[10-projects/数据库 解码器|Database Decoder 工作流]]\n"
        write_file(fpath, c)
        changes.append(f"ironhive/{sub_name[:15]}... +link")

# 4d. sources/中文 LLM 全景 → link to concept
cn_llm = os.path.join(VAULT, "sources", "中文 LLM 全景.md")
c = read_file(cn_llm)
if c and "关联" not in c:
    c = c.rstrip() + "\n\n## 🔗 关联\n\n- [[concepts/LLM 应用 生态|大模型应用生态]]\n- [[synthesis/AI LLM 概览|AI 大模型全景综述]]\n- [[sources/LLMForEverybody/索引|LLMForEverybody 导航]]\n"
    write_file(cn_llm, c)
    changes.append("sources/中文 LLM 全景.md +link")

# 4e. LLMForEverybody drafts → link to index
for draft_name in ["在坚冰还盖着北海的时候，我看到了怒放的梅花", "智能体Agent的5个层次", "仓库"]:
    fpath = os.path.join(VAULT, "sources", "LLMForEverybody", "draft", "md", draft_name + ".md")
    c = read_file(fpath)
    if c and "关联" not in c:
        c = c.rstrip() + "\n\n---\n\n## 🔗 关联\n\n- [[sources/LLMForEverybody/索引|LLMForEverybody 导航总览]]\n"
        write_file(fpath, c)
        changes.append(f"draft/{draft_name[:15]}... +link")

# ═══════════════════════════════════════════════════════
print(f"\nTotal changes: {len(changes)}")
for ch in changes:
    print(f"  + {ch}")
