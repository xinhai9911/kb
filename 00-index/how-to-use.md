# 如何使用本知识库

## 添加一条新笔记

1. 选择合适类别（10-projects / 20-protocols / 30-snippets / 40-ideas / 50-reference）
2. 新建文件，命名用 kebab-case，例如 `influxdb-line-protocol.md`
3. 在文件最上方加 frontmatter：

```yaml
---
title: 简短标题
tags: [tag1, tag2]
status: draft   # draft | active | archived
---
```

4. 写正文。多用双链 `[[20-protocols/influxdb]]` 关联已有笔记
5. commit & push

## 找东西

- GitHub 网页：按 `t` 键（文件查找器），或仓库搜索框 `tags: [protocol]`
- 本地：用 `grep -r "关键词" /q/AI/kb/`
- Obsidian：装在 `Q:\AI\kb`，双链可点跳，全文搜索

## 双链语法

- 同级：`[[influxdb]]` 或 `[[20-protocols/influxdb]]`（推荐带路径，更稳）
- GitHub 不原生支持跳转，需要 Obsidian 或 GitHub 插件

## 提交约定

`<type>: <subject>`，type ∈ {note, fix, refactor, archive, index}

例如：
- `note: add influxdb line protocol analysis`
- `fix: correct hbase command in snippets`
- `index: add recent updates to README`