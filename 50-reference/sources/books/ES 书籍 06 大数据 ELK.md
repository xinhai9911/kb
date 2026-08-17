---
aliases: ["es-book-06-bigdata-elk"]
title: 《大数据搜索与日志挖掘 ELK Stack》蒸馏
tags: [reference, sources, elasticsearch, elk, logstash, kibana, book, active]
created: 2026-07-29
updated: 2026-07-29
source_dir: Q:\常规书籍
source_pdf: 《大数据搜索与日志挖掘及可视化方案ELKStack…(第2版)》.pdf
extract: 文本层提取（291 页，2026-07-29）
base_confidence: 0.85
lifecycle: reviewed
---

# 《大数据搜索与日志挖掘及可视化方案 ELK Stack（第2版）》_高凯等（清华大学出版社，2016）

> 内容来自 **文本层提取（291 页，2026-07-29）** 正文提炼。索引见 [[Elasticsearch ELK]]。

- **定位**：国内较早**综合介绍 ELK 架构**的工程实践教程。以非结构化文本 + 半结构化日志为对象，分三角度：①用 ES（基于 Lucene）做分布式索引与全文检索、数据聚合 ②用 Logstash 智能分析处理日志 ③用 Kibana 做搜索/可视化。书中引 **DB-Engines 2016-01 统计：ES 已超 Solr 成排名第一的搜索引擎类应用**。
- **ELK Stack 组成（含周边）**：Elasticsearch（分布式存储+检索）、Logstash（多源日志处理）、Kibana（可视化）；周边 **Shield**（安全/权限/加密/审计）、**Watcher**（性能监控/告警）、**Beats**（Filebeat/Topbeat/Packetbeat 采集）。
- **章节结构**：ELK 简介 → 文档索引与处理 → 信息检索与过滤 → 信息统计与分析 → 基于 Java 客户端的 ES 功能实现 → ES 配置与管理 → 基于 Logstash 的网络日志处理 → 基于 Kibana 的可视化 → 应用实例。
- **可提炼要点（实证）**：ES 提供分布式计算与全文检索 + 聚合分析；Logstash 处理多源日志；Kibana 出挖掘结果可视化；Shield/Watcher/Beats 是生产增强组件。
- **关联**：与 [[20-protocols/Elasticsearch 2]] 配合作为中文 ELK 实操手册；日志处理链路见 [[50-reference/sources/chips/3 TAP]] 流量可视化。
