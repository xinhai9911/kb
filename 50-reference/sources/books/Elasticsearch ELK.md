---
aliases: ["elasticsearch-elk"]
title: Elasticsearch / ELK 书籍蒸馏索引
tags: [reference, sources, elasticsearch, elk, search, index, active]
created: 2026-07-29
updated: 2026-07-29
summary: >-
  8 本 Elasticsearch / ELK 中文书籍的索引与要点；每本书已拆为独立蒸馏笔记。
category: reference
source_dir: Q:\常规书籍
sources: []
base_confidence: 0.6
lifecycle: reviewed
---

# Elasticsearch / ELK 书籍蒸馏索引

> 8 本 Elasticsearch 与 ELK 栈中文书籍的索引。每本书已拆为独立笔记（见下方列表），各自含内容级蒸馏（真实概念/API/配置示例）。协议层分析见 [[20-protocols/Elasticsearch 2]]。

> ✅ **扫描版 OCR 已完成**：`《深入理解Elasticsearch》.pdf`（270页）、`《Elasticsearch技术解析与实战》.pdf`（436页）原为扫描件、无文本层，已于 2026-07-29 用 EasyOCR（gen2 模型）逐页识别并蒸馏。
> ✅ **全部 8 本均已达内容级蒸馏**：6 本文本层书 + 2 本扫描 OCR 书，均已展开为真实内容，非目录骨架。其中《服务器开发（第2版）》《Kibana 中文指南》于 2026-07-29 完成全量 OCR（457/653 页标记）并蒸馏。
> 原始路径：`Q:\常规书籍\`

## 书目清单与蒸馏笔记（原文路径 `Q:\常规书籍\`）

| # | 书名 | 体量 | 侧重点 | 蒸馏笔记 |
|---|---|---|---|---|
| 1 | 《Elasticsearch实战 in action中文版》_黄申译_2018 | ~186 MB | 实战入门（Manning） | [[ES 书籍 01 实战]] |
| 2 | 《Elasticsearch服务器开发（第2版）》_Clinton Gormely 等 | ~17 MB | 服务端开发（ES 1.0） | [[ES 书籍 02 服务端 开发]] |
| 3 | 《Elasticsearch搜索引擎开发实战》_罗刚等 | ~140 MB | 搜索引擎工程 + Java API | [[ES 书籍 03 搜索 开发]] |
| 4 | 《Kibana 中文指南》 | ~12 MB | Kibana / ELK 可视化 | [[ES 书籍 04 Kibana]] |
| 5 | 《PaaS实现与运维管理：基于Mesos+Docker+ELK》_余何_2016 | ~174 MB | PaaS 中 ELK 落地 | [[ES 书籍 05 PaaS]] |
| 6 | 《大数据搜索与日志挖掘及可视化方案 ELK Stack（第2版）》_高凯等_2016 | ~93 MB | ELK 架构工程实践 | [[ES 书籍 06 大数据 ELK]] |
| 7.1 | 《深入理解Elasticsearch》_Rafał Kuć 等（扫描版·OCR） | ~167 MB | 原理深入（ES 0.90） | [[ES 书籍 07 精通]] |
| 7.2 | 《Elasticsearch技术解析与实战》_朱林（扫描版·OCR） | ~147 MB | 技术原理 + 实战（ES 2.3） | [[ES 书籍 08 技术 分析]] |

## 关键要点（通用索引）

- **集群与索引**：分片、副本、路由、写入/刷新/合并机制（详见 [[ES 书籍 02 服务端 开发]]、[[ES 书籍 08 技术 分析]]）。
- **查询 DSL**：bool / match / term / aggregation，相关性算分（[[ES 书籍 01 实战]]、[[ES 书籍 07 精通]]）。
- **ELK 链路**：Logstash/Beats 采集 → ES 存储 → Kibana 可视化（[[ES 书籍 04 Kibana]]、[[ES 书籍 06 大数据 ELK]]）。
- **运维**：容量规划、监控、故障排查（[[ES 书籍 07 精通]]、[[ES 书籍 05 PaaS]]）。

## 适用场景

- 搭建日志检索/可观测性平台时参考架构与调优。
- 需要中文 Elasticsearch 系统教程时回查对应原书蒸馏笔记。

## 引用

- 协议分析笔记：[[20-protocols/Elasticsearch 2]]
- 源码参考：`Q:\AI\elasticsearch-main\`
- 芯片/硬件对照：[[50-reference/sources/chips/3 TAP]]（流量可视化）、[[50-reference/sources/chips/Centec SDK]]（集群/SDK 接入）
