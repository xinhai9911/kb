---
title: 如何使用本知识库
category: index
summary: >-
    知识库使用说明：页面分类体系、添加笔记、双链语法、提交约定。
created: 2026-07-29
updated: 2026-07-29
sources: []
tags: [kb]
base_confidence: 0.7
lifecycle: reviewed
---

# 如何使用本知识库

本知识库（`Q:\AI\kb`）是 AI 辅助的知识管理 vault，涵盖 AI 大模型、AI Agent、eBPF 内核可编程、数据库协议逆向分析、VPP 网络数据面等方向。所有页面遵循统一的 frontmatter 规范。

## 页面分类体系

| 目录 | 分类 | 内容 |
|------|------|------|
| `concepts/` | **概念** | 跨领域的核心概念（Transformer 架构、MCP 协议、eBPF Maps、LLM 推理优化） |
| `entities/` | **实体** | 公司、产品、工具等具象实体（OpenAI、Anthropic、DeepSeek、Cilium、LangChain） |
| `sources/` | **来源** | 原始资料索引（论文、技术报告、官方文档） |
| `synthesis/` | **综述** | 跨主题的综合性研究综述 |
| `projects/` | **项目** | 实际项目知识（db-decoder-ironhive） |
| `10-projects/` | **项目（旧）** | 遗留项目目录（database-decoder、training） |
| `20-protocols/` | **协议分析** | 数据库/网络协议分析（HBase、ES、InfluxDB、VPP） |
| `30-snippets/` | **代码片段** | 可复用代码片段与模板 |
| `50-reference/` | **参考** | 各类参考文档、ADR |
| `00-index/` | **索引** | 使用说明与标签字典 |
| `_meta/` | **元数据** | 信任账本等内部数据 |

## 添加一条新笔记

1. 根据内容选择正确的分类目录
2. 新建文件，命名用 kebab-case，如 `llm-inference-optimization.md`
3. 在文件最上方加 frontmatter：

```yaml
---
title: 简短标题
category: concepts        # concepts | entities | sources | synthesis | projects | reference
tags: [tag1, tag2]
created: YYYY-MM-DD
updated: YYYY-MM-DD
summary: 一句话摘要
base_confidence: 0.65    # 0.0-1.0 置信度
lifecycle: draft          # draft | active | stable | archived | reviewed
sources: []
---
```

4. 写正文。多用双链 `[[concepts/llm-inference-optimization]]` 关联已有笔记
5. 批量添加后运行 `wiki-lint` 和 `trust-record --all`

## 找东西

- **wiki-query**: 用自然语言搜索知识库（推荐）
- GitHub 网页：按 `t` 键（文件查找器），或仓库搜索框 `tags: [ebpf]`
- 本地：`grep -r "关键词" Q:\AI\kb\`
- Obsidian：装在 `Q:\AI\kb`，双链可点跳，全文搜索

## 双链语法

- 优先用带路径的双链：`[[concepts/transformer-architecture|Transformer]]`
- relationships frontmatter 记录语义关系类型（`uses`、`extends`、`derived_from`、`related_to`）

## 信任框架

每个页面有 `base_confidence`（置信度）和 `lifecycle`（生命周期）：
- **draft**: 初稿，需验证
- **active**: 活跃使用中
- **stable**: 内容稳定，可靠
- **archived**: 过时/已归档
- **reviewed**: 已审查确认

## 提交约定

`<type>: <subject>`，type ∈ {note, fix, refactor, archive, index}

例如：
- `note: add mcp protocol concept page`
- `fix: correct llm inference summary`
- `index: add recent updates to index`
