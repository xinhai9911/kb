---
aliases: ["obsidian-usage"]
title: Obsidian 使用方法
category: reference
tags: [obsidian, tooling, kb, how-to]
created: 2026-07-30
updated: 2026-07-30
summary: >-
    Obsidian 打开本知识库的实操指南：vault 配置、双链/反向链接/关系图谱、
    与本项目约定的配合、推荐插件（Dataview/Graph/Publish）、以及日常检索与维护流程。
base_confidence: 0.9
lifecycle: reviewed
---

# Obsidian 使用方法

本知识库（`Q:\AI\kb`）是一个标准的 Obsidian vault。用 Obsidian 打开后，所有
`[[双链]]` 可点跳、可全文搜索、可看关系图谱。本文是面向本库的 Obsidian 上手与进阶指南。

> 若你还没读过《[[00-index/如何 使用|如何使用本知识库]]》，请先看它了解分类体系与
> frontmatter 规范——本文假设你已知道 `concepts/`、`entities/` 等目录含义。

## 一、把本库作为 Vault 打开

1. 安装 [Obsidian](https://obsidian.md)（Win / macOS / Linux 均免费）。
2. 启动 Obsidian → **Open folder as vault**（或「打开本地仓库」）。
3. 选择目录 `Q:\AI\kb`（即本库根目录，里面有 `concepts/`、`entities/` 等）。
4. 打开后左侧文件树即按目录展示；顶部搜索框可做全文检索。

> 不要把 vault 开到 `Q:\AI` 或 `Q:\AI\kb\concepts`——必须开到 `kb` 根目录，
> 否则 `[[concepts/xxx]]` 这类带路径的双链会解析失败。

## 二、核心概念（3 分钟）

| 概念 | 说明 | 在本库的典型用法 |
|------|------|----------------|
| **双链 `[[...]]`** | 在笔记间建立链接，点击可跳转 | `[[entities/OpenSSL_BoringSSL 开发集成实战\|OpenSSL 实战]]` |
| **反向链接 Backlinks** | 自动列出「哪些笔记链接了我」 | 打开任意概念页，右侧「反向链接」面板可看谁引用了它 |
| **关系图谱 Graph** | 把所有笔记和链接画成网络图 | 全局图谱看知识拓扑；局部图谱看单篇笔记的邻居 |
| **标签 `#tag`** | 用 frontmatter 的 `tags:` 归类 | 本库用 `tags: [ebpf, crypto]` 等做横向检索 |
| **大纲 Outline** | 当前文档的标题层级导航 | 长文（如综述）靠它快速定位章节 |

## 三、导航与检索的几种方式

1. **全文搜索（默认 `Ctrl/Cmd+P` 为快速切换文件，`Ctrl/Cmd+Shift+F` 为全文搜索）**
   - 搜中文关键词（如「熔断器」「ECDHE」）直接命中正文。
2. **快速切换器 (`Ctrl/Cmd+P`)**
   - 输入文件名片段跳转到任意笔记，支持 kebab-case 模糊匹配。
3. **反向链接面板**
   - 想看「某概念被哪些实战/综述引用」，点开该概念页 → 右侧 Backlinks。
4. **关系图谱 (`Ctrl/Cmd+G`)**
   - 全局视图找「孤岛笔记」（无入链/出链）；局部视图（`Ctrl/Cmd+G` 在单页上）看邻居。
5. **标签筛选**
   - 左侧标签面板点 `#crypto` 等，聚合该主题下所有笔记。

## 四、与本库约定的配合

- **带路径的双链**：本库要求 `[[concepts/xxx]]` 而非裸 `[[xxx]]`，避免重名冲突。
  Obsidian 中点击会精确跳到对应目录文件。
- **frontmatter 字段**：
  - `base_confidence`（0.0–1.0）：内容可信度，阅读时先扫一眼。
  - `lifecycle`：`draft`（初稿）/ `active` / `stable` / `reviewed` / `archived`。
    看到 `draft` 应持保留态度。
- **`projects/README` 的搜索**：该页的实时过滤框依赖 HTML/JS，**本地 Obsidian
  不执行 JS**，请用同页底部的「关键词索引（静态查找表）」离线查找。若要在浏览器看
  交互搜索，用 Obsidian Publish 或把 `.md` 转网页后打开。

## 五、推荐插件

| 插件 | 用途 | 对本库价值 |
|------|------|-----------|
| **Dataview** | 用 DSL 查询 frontmatter，动态生成表格 | 可把 `projects/README` 的速览表改成 `TABLE` 查询，自动跟随文件更新 |
| **Graph Analysis / 增强图谱** | 力导布局、按标签着色、找中心节点 | 直观看核心概念（如 eBPF、CPU 架构）的连接密度 |
| **Outliner** | 折叠/缩进列表更顺手 | 写长大纲、协议分析清单时体验更好 |
| **Obsidian Publish**（付费/可自托管） | 把 vault 发布成网站 | 让 `projects/README` 的 JS 搜索框生效，分享给团队 |
| **Linter** | 统一 frontmatter、标题层级 | 批量整理笔记格式，配合 [[00-index/如何 使用|提交约定]] |

> 安装路径：左下角「设置 ⚙」→「社区插件」→「浏览」→ 搜索安装 → 启用。
> 本库未强制要求装插件；纯本地也能正常用双链与搜索。

## 六、日常维护流程（建议）

1. **新增笔记**：按 [[00-index/如何 使用|使用说明]] 建文件 + frontmatter + 带路径双链。
2. **写完即连**：至少链 1–2 篇相关概念/实体，避免产生「孤岛笔记」（图谱里孤立的点）。
3. **随手校验**：
   - 反向链接面板确认新笔记被正确引用；
   - 图谱里看是否出现无连接的孤立节点。
4. **定期跑检查**（仓库层面，非 Obsidian 内）：
   - `wiki-lint`：审计 frontmatter 与链接规范
   - 链接审计脚本：扫 `[[...]]` 断链（见最近一次审计，已修复 CPU/电影人等错链）
5. **提交**：遵循 `<type>: <subject>`（如 `note: add obsidian usage guide`）。

## 七、常见问题（FAQ）

- **双链点不开 / 显示成纯文本？**
  多半是 vault 根目录开错了（开到了子目录），或链接路径写错（如 `concepts/xxx` 实际在
  `entities/`）。用反向链接面板可快速定位谁指向了它。
- **中文文件名双链正常吗？**
  正常。本库大量实体用中文名（如 `[[entities/Nginx 模块开发实战]]`），Obsidian 支持。
- **搜索框在 Obsidian 里不显示？**
  `projects/README` 的搜索框是 HTML/JS，本地不渲染——用底部静态「关键词索引」表，
  或用 Publish/网页版查看交互搜索。
- **图谱太乱看不清？**
  右侧图谱设置里按 `tags` 着色、过滤掉 `lifecycle: archived` 的节点，或只看局部图谱。

## 参考链接

- [[00-index/如何 使用|如何使用本知识库]] — 分类体系与 frontmatter 规范
- [[00-index/标签 术语表|标签字典]] — 标签含义对照
- [[50-reference/Obsidian 插件|Obsidian 已安装插件说明]] — 本库实际装的 11 个社区插件清单
- [[projects/README|工程示例总览导航]] — 含 JS 搜索框与静态关键词索引
- Obsidian 官方文档：<https://help.obsidian.md>
